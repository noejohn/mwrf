import json
import base64
import imghdr
from datetime import date
from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.db import DataError
from django.db.models import Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import TokenError

from .forms import (
    ApprovalForm,
    ChangePasswordForm,
    DepartmentForm,
    MachineForm,
    PersonnelForm,
    RequestForm,
    StatusForm,
    UserProfileForm,
    UserRequestForm,
    UserForm,
    WorkTypeForm,
)
from .models import (
    TblApproval,
    TblDepartment,
    TblMachineGroup,
    TblPersonnel,
    TblRequest,
    TblRequestReference,
    TblStatus,
    TblUsers,
    TblWorkType,
)
from .security import hash_password, is_password_hashed, set_user_password, verify_user_password


ENTITY_CONFIG = {
    "users": {
        "model": TblUsers,
        "form": UserForm,
        "title": "Users",
        "active_page": "users",
        "table_columns": ["userid", "name", "userdepartment", "userposition", "username", "userstatus"],
    },
    "personnel": {
        "model": TblPersonnel,
        "form": PersonnelForm,
        "title": "Personnel",
        "active_page": "personnel",
        "table_columns": ["personnelno", "personnelname", "personneldept", "personneldesig"],
        "column_labels": {
            "personnelno": "No.",
            "personnelname": "Full Name",
            "personneldept": "Department",
            "personneldesig": "Designation",
        },
    },
    "departments": {
        "model": TblDepartment,
        "form": DepartmentForm,
        "title": "Departments",
        "active_page": "department",
        "table_columns": ["deptno", "depname"],
    },
    "machines": {
        "model": TblMachineGroup,
        "form": MachineForm,
        "title": "Machines",
        "active_page": "machine",
        "table_columns": ["machineno", "machinename"],
        "column_labels": {
            "machineno": "No.",
            "machinename": "Machine Group",
        },
    },
    "work-types": {
        "model": TblWorkType,
        "form": WorkTypeForm,
        "title": "Work Types",
        "active_page": "worktype",
        "table_columns": ["workno", "worktype"],
        "column_labels": {
            "workno": "No.",
            "worktype": "Work Type",
        },
    },
    "statuses": {
        "model": TblStatus,
        "form": StatusForm,
        "title": "Statuses",
        "active_page": "status",
        "table_columns": ["statusno", "status"],
        "column_labels": {
            "statusno": "No.",
            "status": "Status",
        },
    },
    "approvals": {
        "model": TblApproval,
        "form": ApprovalForm,
        "title": "Approving Personnel",
        "active_page": "approval",
        "table_columns": ["approvalno", "approvalname", "approvaldept"],
        "column_labels": {
            "approvalno": "No.",
            "approvalname": "Full Name",
            "approvaldept": "Department",
        },
        "manual_pk": True,
    },
}

REQUEST_FILTER_LABELS = {
    "all": "All Machine Request",
    "current": "Current / Approval Queue",
    "on-going": "On going machine request",
    "verification": "Verification Requests",
    "done": "Closed machine work request",
    "rejected": "Rejected machine request",
    "backjob": "Backjob machine request",
}

STATUS_PENDING_APPROVAL = "PENDING APPROVAL"
STATUS_APPROVED = "APPROVED"
STATUS_ON_GOING = "ON GOING"
STATUS_FOR_VERIFICATION = "FOR VERIFICATION"
STATUS_BACK_JOB = "BACK JOB"
STATUS_CLOSED = "CLOSED"
STATUS_REJECTED = "REJECTED"

REQUEST_FINDINGS_OPTIONS = [
    "VERIFIED",
    "BACK JOB",
    "REJECTED",
]

REQUEST_TABLE_COLUMNS_SUPERADMIN = [
    ("row_no", "#"),
    ("requestno", "Request No."),
    ("requestdate", "Date Requested"),
    ("requestor", "Requestor"),
    ("department", "Department"),
    ("requestdept", "Requested Department"),
    ("machinegroup", "Machine Group"),
    ("worktype", "Type of Work"),
    ("approval", "Approval Person"),
    ("description", "Description"),
    ("dateneeded", "Date Needed"),
    ("personnel", "Assigned Personnel"),
    ("notes", "Requestee's Note"),
    ("dateupdated", "Date Updated"),
    ("verifiedby", "Verified By"),
    ("findings", "Findings"),
    ("verifiednote", "Verifier's Note"),
    ("verifieddate", "Date Verified"),
    ("status", "Status"),
]

REQUEST_TABLE_COLUMNS_STANDARD = [
    ("row_no", "#"),
    ("requestno", "Request No."),
    ("requestdate", "Date Requested"),
    ("requestor", "Requestor"),
    ("department", "Department"),
    ("requestdept", "Req. Dept."),
    ("machinegroup", "Machine"),
    ("worktype", "Work Type"),
    ("status", "Status"),
]

ROLE_SUPERADMIN = "superadmin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ALLOWED_DASHBOARD_ROLES = {ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_USER}
ADMIN_MANAGEABLE_ENTITIES = {"machines", "work-types", "statuses", "approvals", "personnel"}
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def _next_pk(model):
    pk_name = model._meta.pk.name
    max_pk = model.objects.aggregate(max_pk=Max(pk_name)).get("max_pk") or 0
    return max_pk + 1


def _normalize_status(value):
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _status_equals(left, right):
    return _normalize_status(left) == _normalize_status(right)


def _is_pending_approval_status(value):
    normalized = _normalize_status(value)
    if not normalized or normalized == "new":
        return True
    return normalized in {_normalize_status(STATUS_PENDING_APPROVAL), "pending"}


def _is_approved_status(value):
    return _status_equals(value, STATUS_APPROVED)


def _is_on_going_status(value):
    normalized = _normalize_status(value)
    return normalized in {_normalize_status(STATUS_ON_GOING), "ongoing"}


def _is_verification_status(value):
    normalized = _normalize_status(value)
    return normalized in {_normalize_status(STATUS_FOR_VERIFICATION), "verification"} or "verify" in normalized


def _is_back_job_status(value):
    return _status_equals(value, STATUS_BACK_JOB)


def _is_closed_status(value):
    normalized = _normalize_status(value)
    return normalized in {_normalize_status(STATUS_CLOSED), "done", "complete", "verified"}


def _is_rejected_status(value):
    normalized = _normalize_status(value)
    return normalized in {_normalize_status(STATUS_REJECTED), "reject", "rejected"}


def _canonical_status(value):
    if _is_closed_status(value):
        return STATUS_CLOSED
    if _is_rejected_status(value):
        return STATUS_REJECTED
    if _is_back_job_status(value):
        return STATUS_BACK_JOB
    if _is_verification_status(value):
        return STATUS_FOR_VERIFICATION
    if _is_on_going_status(value):
        return STATUS_ON_GOING
    if _is_approved_status(value):
        return STATUS_APPROVED
    if _is_pending_approval_status(value):
        return STATUS_PENDING_APPROVAL
    return str(value or "").strip()


def _status_category(value):
    if _is_rejected_status(value):
        return "rejected"
    if _is_back_job_status(value):
        return "backjob"
    if _is_verification_status(value):
        return "verification"
    if _is_on_going_status(value):
        return "on-going"
    if _is_closed_status(value):
        return "done"
    if _is_pending_approval_status(value) or _is_approved_status(value):
        return "new"
    return "other"


def _match_request_filter(request_obj, filter_key):
    category = _status_category(request_obj.status)
    personnel_value = str(getattr(request_obj, "personnel", "") or "").strip()
    has_assigned_personnel = bool(personnel_value) and personnel_value.upper() != "UNASSIGNED"
    if filter_key == "all":
        return True
    if filter_key == "current":
        return category == "new"
    if filter_key == "on-going":
        return category == "on-going" and has_assigned_personnel
    return category == filter_key


def _get_session_user(request):
    user_id = request.session.get("mwrf_user_id")
    if not user_id:
        return None
    try:
        return TblUsers.objects.get(userid=user_id)
    except TblUsers.DoesNotExist:
        return None


def _resolve_role(position):
    normalized = "".join(ch for ch in (position or "").lower() if ch.isalnum())
    if "super" in normalized and "admin" in normalized:
        return ROLE_SUPERADMIN
    if "admin" in normalized:
        return ROLE_ADMIN
    return ROLE_USER


def _department_approver_map():
    department_map = {
        str(dep or "").strip(): []
        for dep in TblDepartment.objects.order_by("depname").values_list("depname", flat=True)
        if str(dep or "").strip()
    }
    approvals = TblApproval.objects.order_by("approvaldept", "approvalname").only("approvaldept", "approvalname")
    for item in approvals:
        department = str(item.approvaldept or "").strip()
        name = str(item.approvalname or "").strip()
        if not department or not name:
            continue
        department_items = department_map.setdefault(department, [])
        if name not in department_items:
            department_items.append(name)
    return department_map


def _approval_admins_by_department():
    mapping = {"": []}
    approvals = TblApproval.objects.order_by("approvaldept", "approvalname").only("approvalname", "approvaldept")
    for item in approvals:
        name = str(item.approvalname or "").strip()
        department = str(item.approvaldept or "").strip()
        if not name:
            continue
        if name not in mapping[""]:
            mapping[""].append(name)
        if department:
            department_items = mapping.setdefault(department, [])
            if name not in department_items:
                department_items.append(name)
    return mapping


def _department_personnel_map():
    mapping = {"": []}
    personnel_rows = TblPersonnel.objects.order_by("personnelname").only("personnelname", "personneldept")
    for item in personnel_rows:
        name = str(item.personnelname or "").strip()
        department = str(item.personneldept or "").strip()
        if not name:
            continue
        if name not in mapping[""]:
            mapping[""].append(name)
        if department:
            dept_items = mapping.setdefault(department, [])
            if name not in dept_items:
                dept_items.append(name)
    return mapping


def _request_status_options():
    values = []
    seen = set()
    for item in TblStatus.objects.order_by("status").values_list("status", flat=True):
        status_text = str(item or "").strip()
        normalized = _normalize_status(status_text)
        if status_text and normalized and normalized not in seen:
            seen.add(normalized)
            values.append(status_text)
    return values


def _is_approval_person(user):
    name = str(getattr(user, "name", "") or "").strip()
    if not name:
        return False
    return TblApproval.objects.filter(approvalname__iexact=name).exists()


def _is_assigned_approver_for_request(user, request_obj):
    approver_name = str(getattr(request_obj, "approval", "") or "").strip().lower()
    current_name = str(getattr(user, "name", "") or "").strip().lower()
    if not approver_name or not current_name:
        return False
    return approver_name == current_name


def _is_request_department_admin(user, role, request_obj):
    if role == ROLE_SUPERADMIN:
        return True
    if role != ROLE_ADMIN:
        return False
    department = str(getattr(user, "userdepartment", "") or "").strip().lower()
    requested_department = str(getattr(request_obj, "requestdept", "") or "").strip().lower()
    if not department or not requested_department:
        return False
    return department == requested_department


def _build_permissions(role, user=None):
    if role == ROLE_SUPERADMIN:
        return {
            "can_view_dashboard": True,
            "can_manage_users": True,
            "can_manage_departments": True,
            "can_manage_personnel": True,
            "can_manage_machines": True,
            "can_manage_worktypes": True,
            "can_manage_statuses": True,
            "can_manage_approvals": True,
            "can_view_requests": True,
            "can_request_action": True,
            "can_request_operations": True,
            "can_request_approval": True,
            "can_request_verification_fields": True,
            "can_request_create": True,
            "can_request_delete": True,
            "can_toggle_users": True,
        }

    is_approval_person = bool(user is not None and _is_approval_person(user))
    can_request_operations = role == ROLE_SUPERADMIN or is_approval_person
    # Approval persons are limited to operational request fields only.
    # Full approval/verification controls stay with admin/superadmin accounts
    # that are not tagged as approval persons.
    can_request_approval = role == ROLE_SUPERADMIN or (role == ROLE_ADMIN and not is_approval_person)
    can_request_action = can_request_operations or can_request_approval

    return {
        "can_view_dashboard": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
        "can_manage_users": role == ROLE_SUPERADMIN,
        "can_manage_departments": role == ROLE_SUPERADMIN,
        "can_manage_personnel": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
        "can_manage_machines": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
        "can_manage_worktypes": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
        "can_manage_statuses": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
        "can_manage_approvals": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
        "can_view_requests": role in ALLOWED_DASHBOARD_ROLES,
        "can_request_action": can_request_action,
        "can_request_operations": can_request_operations,
        "can_request_approval": can_request_approval,
        "can_request_verification_fields": can_request_approval,
        "can_request_create": role in {ROLE_SUPERADMIN, ROLE_USER},
        "can_request_delete": role == ROLE_SUPERADMIN,
        "can_toggle_users": role == ROLE_SUPERADMIN,
    }


def _can_manage_entity(role, entity):
    if role == ROLE_SUPERADMIN:
        return True
    if role == ROLE_ADMIN:
        return entity in ADMIN_MANAGEABLE_ENTITIES
    return False


def _ensure_default_admin_user():
    try:
        if TblUsers.objects.filter(username__iexact=DEFAULT_ADMIN_USERNAME).exists():
            pass
        else:
            default_department = (
                TblDepartment.objects.order_by("deptno").values_list("depname", flat=True).first() or "ADMIN"
            )
            TblUsers.objects.create(
                name="Admin",
                userdepartment=default_department[:50],
                useraddress="N/A",
                usercontact="0000000000",
                userposition="ADMIN",
                username=DEFAULT_ADMIN_USERNAME,
                userpassword=hash_password(DEFAULT_ADMIN_PASSWORD),
                userstatus="ACTIVE",
                userimage=b"",
            )
        # One-time safety upgrade path for any existing plain-text rows.
        for item in TblUsers.objects.all().only("userid", "userpassword"):
            if not is_password_hashed(item.userpassword):
                set_user_password(item, item.userpassword, save=True)
    except Exception:
        return


def superadmin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = _get_session_user(request)
        if not user:
            messages.error(request, "Please log in first.")
            return redirect("login")
        role = _resolve_role(request.session.get("mwrf_role") or user.userposition)
        if role not in ALLOWED_DASHBOARD_ROLES:
            request.session.flush()
            messages.error(request, "Only authorized accounts can access this page.")
            return redirect("login")
        request.session["mwrf_role"] = role
        request.session["mwrf_role_label"] = user.userposition
        request.current_user = user
        request.current_role = role
        request.current_permissions = _build_permissions(role, user=user)
        return view_func(request, *args, **kwargs)

    return wrapped


def login_page(request):
    _ensure_default_admin_user()
    initial_error = ""
    pending_messages = list(messages.get_messages(request))
    if pending_messages:
        initial_error = str(pending_messages[0])
    return render(request, "accounts/login.html", {"initial_error": initial_error})


@csrf_exempt
def login_api(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {}

    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    if not username or not password:
        return JsonResponse({"ok": False, "message": "Username and password are required."}, status=400)

    _ensure_default_admin_user()

    user = TblUsers.objects.filter(username__iexact=username).first()
    if not user or not verify_user_password(user, password):
        return JsonResponse({"ok": False, "message": "Invalid username or password."}, status=401)

    if (user.userstatus or "").upper() != "ACTIVE":
        return JsonResponse({"ok": False, "message": "This user is inactive."}, status=403)

    role = _resolve_role(user.userposition)
    if role not in ALLOWED_DASHBOARD_ROLES:
        return JsonResponse({"ok": False, "message": "This account is not allowed to log in to this dashboard."}, status=403)

    request.session["mwrf_user_id"] = user.userid
    request.session["mwrf_user_name"] = user.name
    request.session["mwrf_role"] = role
    request.session["mwrf_role_label"] = user.userposition

    refresh = RefreshToken()
    refresh["user_id"] = str(user.userid)
    refresh["username"] = str(user.username or "")
    refresh["name"] = str(user.name or "")
    refresh["role"] = role
    access = refresh.access_token
    return JsonResponse(
        {
            "ok": True,
            "redirect": reverse("core:dashboard_home"),
            "access_token": str(access),
            "refresh_token": str(refresh),
            "token_type": "Bearer",
            "expires_in": int(access.lifetime.total_seconds()),
        }
    )


def register_page(request):
    departments = list(TblDepartment.objects.order_by("depname").values_list("depname", flat=True))
    return render(
        request,
        "accounts/register.html",
        {
            "departments_json": json.dumps(departments),
        },
    )


@csrf_exempt
def register_api(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {}

    fullname = str(payload.get("fullname", "")).strip()
    department = str(payload.get("department", "")).strip()
    address = str(payload.get("address", "")).strip()
    contact = str(payload.get("contact", "")).strip()
    password = str(payload.get("password", ""))
    consent = bool(payload.get("consent", False))

    if not fullname or not department or not address or not contact or not password:
        return JsonResponse({"ok": False, "message": "All fields are required."}, status=400)

    if len(fullname) > 50 or len(department) > 50 or len(address) > 25 or len(contact) > 15 or len(password) > 50:
        return JsonResponse({"ok": False, "message": "One or more fields exceed allowed length."}, status=400)

    if len(password) < 6:
        return JsonResponse({"ok": False, "message": "Password must be at least 6 characters."}, status=400)

    if not consent:
        return JsonResponse({"ok": False, "message": "You must accept the data privacy consent."}, status=400)

    dep_exists = TblDepartment.objects.filter(depname__iexact=department).exists()
    if not dep_exists:
        return JsonResponse({"ok": False, "message": "Selected department does not exist."}, status=400)

    base_username = "".join(ch.lower() for ch in fullname if ch.isalnum())[:18] or "user"
    username = base_username
    suffix = 1
    while TblUsers.objects.filter(username__iexact=username).exists():
        username = f"{base_username}{suffix}"
        suffix += 1

    TblUsers.objects.create(
        name=fullname[:50],
        userdepartment=department[:50],
        useraddress=address[:25],
        usercontact=contact[:15],
        userposition="USER",
        username=username,
        userpassword=hash_password(password[:50]),
        userstatus="INACTIVE",
        userimage=b"",
    )

    return JsonResponse(
        {
            "ok": True,
            "message": "Registration submitted. Wait for super admin activation.",
            "username": username,
        }
    )


@csrf_exempt
def verify_jwt_api(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        payload = {}

    auth_header = str(request.headers.get("Authorization", "") or "").strip()
    token = str(payload.get("token", "") or "").strip()
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return JsonResponse({"ok": False, "message": "Token is required."}, status=400)

    try:
        decoded = UntypedToken(token)
    except TokenError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=401)

    user_id = decoded.get("user_id")
    user = TblUsers.objects.filter(userid=user_id).first()
    if not user:
        return JsonResponse({"ok": False, "message": "User not found for token."}, status=401)
    if (user.userstatus or "").upper() != "ACTIVE":
        return JsonResponse({"ok": False, "message": "User is inactive."}, status=403)

    return JsonResponse(
        {
            "ok": True,
            "payload": {
                "sub": str(user.userid),
                "username": str(user.username or ""),
                "name": str(user.name or ""),
                "role": decoded.get("role") or _resolve_role(user.userposition),
                "exp": decoded.get("exp"),
                "iat": decoded.get("iat"),
            },
        }
    )


def logout_view(request):
    request.session.flush()
    return redirect("login")


@superadmin_required
def dashboard_home(request):
    if request.current_role == ROLE_USER:
        return redirect("core:request_list")

    requests_qs = list(TblRequest.objects.all().order_by("-requestno"))
    counts = {
        "all": len(requests_qs),
        "new": 0,
        "on_going": 0,
        "verification": 0,
        "done": 0,
        "rejected": 0,
        "backjob": 0,
    }
    for item in requests_qs:
        category = _status_category(item.status)
        normalized_category = "on_going" if category == "on-going" else category
        if normalized_category in counts:
            counts[normalized_category] += 1

    status_rows = [
        ("Current / Approval", counts["new"]),
        ("On-going", counts["on_going"]),
        ("Verification", counts["verification"]),
        ("Closed", counts["done"]),
        ("Rejected", counts["rejected"]),
        ("Back-job", counts["backjob"]),
    ]

    dashboard_ui = _build_dashboard_ui_payload(requests_qs, counts, status_rows)
    return _render_core_react_page(request, "home", "dashboard", dashboard_ui)


@superadmin_required
def profile_settings(request):
    user = request.current_user

    if request.method == "POST":
        action = str(request.POST.get("action", "")).strip().lower()
        if action == "profile":
            profile_form = UserProfileForm(request.POST, request.FILES, instance=user)
            password_form = ChangePasswordForm(user=user)
            if profile_form.is_valid():
                updated = profile_form.save()
                request.session["mwrf_user_name"] = updated.name
                messages.success(request, "Profile updated successfully.")
                return redirect("core:profile_settings")
        elif action == "password":
            profile_form = UserProfileForm(instance=user)
            password_form = ChangePasswordForm(request.POST, user=user)
            if password_form.is_valid():
                set_user_password(user, password_form.cleaned_data["new_password"], save=True)
                messages.success(request, "Password changed successfully.")
                return redirect("core:profile_settings")
        else:
            profile_form = UserProfileForm(instance=user)
            password_form = ChangePasswordForm(user=user)
    else:
        profile_form = UserProfileForm(instance=user)
        password_form = ChangePasswordForm(user=user)

    current_user = TblUsers.objects.get(userid=user.userid)
    profile_ui = _build_profile_ui_payload(current_user, profile_form, password_form)
    return _render_core_react_page(request, "profile", "profile", profile_ui)


def _entity_or_404(entity):
    config = ENTITY_CONFIG.get(entity)
    if not config:
        raise Http404("Entity not found.")
    return config


def _profile_image_data_uri(user):
    raw = bytes(getattr(user, "userimage", b"") or b"")
    if not raw:
        return ""
    image_type = imghdr.what(None, h=raw) or "jpeg"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/{image_type};base64,{encoded}"


def _save_request_reference_file(request_obj, uploaded_file):
    if not uploaded_file:
        return

    raw = uploaded_file.read() or b""
    if not raw:
        return

    filename = str(getattr(uploaded_file, "name", "") or "").strip()[:255]
    content_type = str(getattr(uploaded_file, "content_type", "") or "").strip()[:100]
    record = TblRequestReference.objects.filter(requestno=request_obj.requestno).first()
    if record:
        record.filename = filename
        record.contenttype = content_type
        record.filedata = raw
        record.uploadedat = timezone.localdate()
        record.save(update_fields=["filename", "contenttype", "filedata", "uploadedat"])
        return

    TblRequestReference.objects.create(
        requestno=request_obj.requestno,
        filename=filename,
        contenttype=content_type,
        filedata=raw,
        uploadedat=timezone.localdate(),
    )


def _request_reference_map(records):
    request_ids = [int(item.requestno) for item in records if getattr(item, "requestno", None) is not None]
    if not request_ids:
        return {}

    mapping = {}
    for ref in TblRequestReference.objects.filter(requestno__in=request_ids).only("requestno", "filename", "contenttype"):
        mapping[int(ref.requestno)] = {
            "filename": str(ref.filename or "").strip(),
            "contenttype": str(ref.contenttype or "").strip(),
        }
    return mapping


def _build_dashboard_ui_payload(requests_qs, counts, status_rows):
    return {
        "counts": counts,
        "statusRows": [{"label": label, "count": count} for label, count in status_rows],
        "recentRequests": [
            {
                "requestno": item.requestno,
                "requestor": item.requestor or "",
                "machinegroup": item.machinegroup or "",
                "worktype": item.worktype or "",
                "requestdate": str(item.requestdate or ""),
                "status": item.status or "",
            }
            for item in requests_qs[:10]
        ],
        "quickLinks": {
            "newRequest": reverse("core:request_list"),
            "verification": reverse("core:request_list_filtered", kwargs={"filter_key": "verification"}),
            "onGoing": reverse("core:request_list_filtered", kwargs={"filter_key": "on-going"}),
            "rejected": reverse("core:request_list_filtered", kwargs={"filter_key": "rejected"}),
        },
    }


def _serialize_form_fields(form):
    return [
        {
            "name": field.name,
            "label": field.label,
            "widgetHtml": str(field),
            "errors": [str(error) for error in field.errors],
        }
        for field in form
    ]


def _build_shell_ui_payload(request, active_page):
    permissions = request.current_permissions
    menu_sections = []
    is_user_role = request.current_role == ROLE_USER

    general_items = []
    if permissions.get("can_view_dashboard"):
        general_items.append(
            {
                "key": "home",
                "label": "Home",
                "url": reverse("core:dashboard_home"),
            }
        )
    general_items.append(
        {
            "key": "profile",
            "label": "Settings",
            "url": reverse("core:profile_settings"),
        }
    )
    if permissions.get("can_manage_users"):
        general_items.append(
            {
                "key": "users",
                "label": "Users",
                "url": reverse("core:entity_list", kwargs={"entity": "users"}),
            }
        )
    if permissions.get("can_manage_personnel"):
        general_items.append(
            {
                "key": "personnel",
                "label": "Personnel",
                "url": reverse("core:entity_list", kwargs={"entity": "personnel"}),
            }
        )
    if permissions.get("can_manage_departments"):
        general_items.append(
            {
                "key": "department",
                "label": "Department",
                "url": reverse("core:entity_list", kwargs={"entity": "departments"}),
            }
        )
    if permissions.get("can_manage_machines"):
        general_items.append(
            {
                "key": "machine",
                "label": "Machine",
                "url": reverse("core:entity_list", kwargs={"entity": "machines"}),
            }
        )
    if permissions.get("can_manage_worktypes"):
        general_items.append(
            {
                "key": "worktype",
                "label": "Work Type",
                "url": reverse("core:entity_list", kwargs={"entity": "work-types"}),
            }
        )
    menu_sections.append({"heading": "GENERAL", "items": general_items})

    request_items = []
    if permissions.get("can_manage_approvals"):
        request_items.append(
            {
                "key": "approval",
                "label": "Approval",
                "url": reverse("core:entity_list", kwargs={"entity": "approvals"}),
            }
        )
    if permissions.get("can_manage_statuses"):
        request_items.append(
            {
                "key": "status",
                "label": "Status",
                "url": reverse("core:entity_list", kwargs={"entity": "statuses"}),
            }
        )
    if permissions.get("can_view_requests"):
        if is_user_role:
            request_items.extend(
                [
                    {
                        "key": "makerequest",
                        "label": "Make Request",
                        "url": reverse("core:request_make"),
                    },
                    {
                        "key": "myrequest",
                        "label": "My Request",
                        "url": reverse("core:request_my"),
                    },
                ]
            )
        else:
            request_items.append(
                {
                    "key": "allrequest",
                    "label": "All Request",
                    "url": reverse("core:request_list"),
                }
            )
        if permissions.get("can_request_action") and not is_user_role:
            request_items.extend(
                [
                    {
                        "key": "current",
                        "label": "Current",
                        "url": reverse("core:request_list_filtered", kwargs={"filter_key": "current"}),
                    },
                    {
                        "key": "on-going",
                        "label": "On-going",
                        "url": reverse("core:request_list_filtered", kwargs={"filter_key": "on-going"}),
                    },
                    {
                        "key": "verification",
                        "label": "Verification",
                        "url": reverse("core:request_list_filtered", kwargs={"filter_key": "verification"}),
                    },
                    {
                        "key": "done",
                        "label": "Closed",
                        "url": reverse("core:request_list_filtered", kwargs={"filter_key": "done"}),
                    },
                    {
                        "key": "rejected",
                        "label": "Rejected",
                        "url": reverse("core:request_list_filtered", kwargs={"filter_key": "rejected"}),
                    },
                    {
                        "key": "backjob",
                        "label": "Back Job",
                        "url": reverse("core:request_list_filtered", kwargs={"filter_key": "backjob"}),
                    },
                ]
            )
    if request_items:
        menu_sections.append({"heading": "REQUESTS", "items": request_items})

    return {
        "activePage": active_page,
        "currentUser": {
            "name": str(request.current_user.name or "").strip() or "Super Admin",
        },
        "logoutUrl": reverse("logout"),
        "menuSections": menu_sections,
        "messages": [str(item) for item in messages.get_messages(request)],
    }


def _build_profile_ui_payload(current_user, profile_form, password_form):
    profile_name = str(current_user.name or "").strip()
    return {
        "profileImageData": _profile_image_data_uri(current_user),
        "profileInitial": (profile_name[:1] or "U").upper(),
        "user": {
            "userid": current_user.userid,
            "name": current_user.name or "",
            "username": current_user.username or "",
            "department": current_user.userdepartment or "",
            "address": current_user.useraddress or "",
            "contact": current_user.usercontact or "",
            "position": current_user.userposition or "",
            "status": current_user.userstatus or "",
        },
        "profileFormFields": _serialize_form_fields(profile_form),
        "passwordFormFields": _serialize_form_fields(password_form),
    }


def _render_core_react_page(request, active_page, page_type, page_payload):
    return render(
        request,
        "core/app_react.html",
        {
            "shell_ui": _build_shell_ui_payload(request, active_page),
            "page_type": page_type,
            "page_payload": page_payload,
        },
    )


def _build_entity_ui_payload(entity, config, form, records, editing):
    column_labels = config.get("column_labels", {})
    table_headers = [{"key": col, "label": column_labels.get(col, col)} for col in config["table_columns"]]
    rows = []
    for row in records:
        row_values = {col: str(getattr(row, col, "") or "") for col in config["table_columns"]}
        rows.append(
            {
                "pk": row.pk,
                "values": row_values,
                "userstatus": str(getattr(row, "userstatus", "") or ""),
            }
        )

    form_fields = _serialize_form_fields(form)

    payload = {
        "entity": entity,
        "title": config["title"],
        "editing": bool(editing),
        "tableHeaders": table_headers,
        "tableColumns": config["table_columns"],
        "records": rows,
        "formFields": form_fields,
        "emptyColspan": len(config["table_columns"]) + 1,
        "urls": {
            "cancel": reverse("core:entity_list", kwargs={"entity": entity}),
            "editTemplate": reverse("core:entity_edit", kwargs={"entity": entity, "pk": 0}),
            "deleteTemplate": reverse("core:entity_delete", kwargs={"entity": entity, "pk": 0}),
            "toggleUserTemplate": reverse("core:toggle_user_status", kwargs={"pk": 0}) if entity == "users" else "",
        },
    }
    if entity == "approvals":
        approval_dept_options = []
        selected_approval_dept = ""
        selected_approval_name = ""
        if "approvaldept" in form.fields:
            approval_dept_options = [
                {"value": str(value or ""), "label": str(label or "")}
                for value, label in form.fields["approvaldept"].choices
            ]
            selected_approval_dept = str(form["approvaldept"].value() or "").strip()
        if "approvalname" in form.fields:
            selected_approval_name = str(form["approvalname"].value() or "").strip()

        payload["approvalDeptOptions"] = approval_dept_options
        payload["approvalAdminsByDepartment"] = _approval_admins_by_department()
        payload["selectedApprovalDept"] = selected_approval_dept
        payload["selectedApprovalName"] = selected_approval_name
    return payload


def _build_request_ui_payload(
    request,
    filter_key,
    form,
    records,
    counts,
    query,
    is_user_request_mode,
    user_page_mode,
    is_superadmin,
    today_date,
    next_request_no,
):
    reference_map = _request_reference_map(records)

    def _string(value, default="-"):
        text = str(value or "").strip()
        return text if text else default

    def _serialize_request(req, index):
        verified_by_value = _string(req.verifiedby)
        verified_date_value = _string(req.verifieddate) if verified_by_value != "-" else "-"
        reference_payload = reference_map.get(int(req.requestno), {})
        reference_name = str(reference_payload.get("filename", "")).strip()
        reference_content_type = str(reference_payload.get("contenttype", "")).strip()
        has_reference = bool(reference_name)
        return {
            "row_no": index,
            "requestno": str(req.requestno),
            "requestdate": _string(req.requestdate),
            "requestor": _string(req.requestor),
            "department": _string(req.department),
            "requestdept": _string(req.requestdept),
            "machinegroup": _string(req.machinegroup),
            "worktype": _string(req.worktype),
            "approval": _string(req.approval),
            "description": _string(req.description),
            "dateneeded": _string(req.dateneeded),
            "personnel": _string(req.personnel),
            "status": _string(req.status),
            "notes": _string(req.notes),
            "dateupdated": _string(req.dateupdated),
            "verifiedby": verified_by_value,
            "findings": _string(req.findings),
            "verifiednote": _string(req.verifiednote),
            "verifieddate": verified_date_value,
            "hasReferenceFile": has_reference,
            "referenceFileName": reference_name,
            "referenceContentType": reference_content_type,
            "referenceFileUrl": reverse("core:request_reference_file", kwargs={"pk": int(req.requestno)}) if has_reference else "",
            "referenceIsImage": reference_content_type.lower().startswith("image/"),
            "referenceIsVideo": reference_content_type.lower().startswith("video/"),
        }

    form_fields = []
    form_fields_by_name = {}
    for field in form:
        payload = {
            "name": field.name,
            "label": field.label,
            "widgetHtml": str(field),
            "errors": [str(error) for error in field.errors],
        }
        form_fields.append(payload)
        form_fields_by_name[field.name] = payload

    serialized_records = []
    for index, req in enumerate(records, start=1):
        serialized_records.append(_serialize_request(req, index))

    ongoing_records = [
        _serialize_request(req, index)
        for index, req in enumerate(records, start=1)
        if _status_category(req.status) == "on-going"
    ]

    headers = REQUEST_TABLE_COLUMNS_SUPERADMIN if is_superadmin else REQUEST_TABLE_COLUMNS_STANDARD
    table_headers = [{"key": key, "label": label} for key, label in headers]

    request_dept_options = []
    selected_request_dept = ""
    selected_approval = ""
    if is_user_request_mode and "requestdept" in form.fields:
        requestdept_field = form.fields["requestdept"]
        field_choices = getattr(requestdept_field, "choices", None)
        if field_choices is not None:
            request_dept_options = [{"value": str(value or ""), "label": str(label or "")} for value, label in field_choices]
        selected_request_dept = str(form["requestdept"].value() or "").strip()
    selected_approval_department = ""
    if is_user_request_mode and "requestdept" in form.fields:
        selected_approval_department = str(form["requestdept"].value() or "").strip()
    if is_user_request_mode and "approval" in form.fields:
        selected_approval = str(form["approval"].value() or "").strip()

    payload = {
        "filterKey": filter_key,
        "filterLabel": REQUEST_FILTER_LABELS[filter_key],
        "query": query,
        "counts": counts,
        "isUserRequestMode": is_user_request_mode,
        "userPageMode": user_page_mode,
        "isSuperadmin": is_superadmin,
        "isDoneFilter": filter_key == "done",
        "todayDate": str(today_date),
        "nextRequestNo": next_request_no,
        "tableHeaders": table_headers,
        "emptyColspan": len(table_headers),
        "records": serialized_records,
        "ongoingRecords": ongoing_records,
        "formFields": form_fields,
        "formFieldsByName": form_fields_by_name,
        "requestDeptOptions": request_dept_options,
        "departmentApprovers": _department_approver_map() if is_user_request_mode else {},
        "selectedApprovalDepartment": selected_approval_department,
        "selectedRequestedDept": selected_request_dept,
        "selectedApproval": selected_approval,
        "permissions": {
            "canRequestCreate": bool(request.current_permissions.get("can_request_create")),
            "canRequestAction": bool(request.current_permissions.get("can_request_action")),
            "canRequestOperations": bool(request.current_permissions.get("can_request_operations")),
            "canRequestApproval": bool(request.current_permissions.get("can_request_approval")),
            "canRequestVerificationFields": bool(request.current_permissions.get("can_request_verification_fields")),
            "canRequestDelete": bool(request.current_permissions.get("can_request_delete")),
        },
        "workflowStatuses": {
            "pendingApproval": STATUS_PENDING_APPROVAL,
            "approved": STATUS_APPROVED,
            "onGoing": STATUS_ON_GOING,
            "forVerification": STATUS_FOR_VERIFICATION,
            "backJob": STATUS_BACK_JOB,
            "closed": STATUS_CLOSED,
            "rejected": STATUS_REJECTED,
        },
        "urls": {
            "allRequests": reverse("core:request_list"),
            "onGoingFilter": reverse("core:request_list_filtered", kwargs={"filter_key": "on-going"}),
            "approveTemplate": reverse("core:request_action", kwargs={"pk": 0, "action": "approve"}),
            "rejectTemplate": reverse("core:request_action", kwargs={"pk": 0, "action": "reject"}),
            "updateTemplate": reverse("core:request_action", kwargs={"pk": 0, "action": "update"}),
            "deleteTemplate": reverse("core:request_delete", kwargs={"pk": 0}),
            "userVerifyTemplate": reverse("core:request_user_verify", kwargs={"pk": 0}),
            "userBackjobTemplate": reverse("core:request_user_backjob", kwargs={"pk": 0}),
        },
    }
    if not is_user_request_mode:
        payload["personnelByDepartment"] = _department_personnel_map()
        payload["requestStatusOptions"] = _request_status_options()
        payload["findingsOptions"] = REQUEST_FINDINGS_OPTIONS
        payload["currentApproverName"] = str(request.current_user.name or "").strip()
    return payload


@superadmin_required
def entity_list(request, entity):
    if not _can_manage_entity(request.current_role, entity):
        messages.error(request, "You do not have permission to manage this module.")
        return redirect("core:dashboard_home")

    config = _entity_or_404(entity)
    model = config["model"]
    form_class = config["form"]
    pk_name = model._meta.pk.name

    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            if config.get("manual_pk"):
                setattr(obj, pk_name, _next_pk(model))
            if entity == "users" and not obj.userstatus:
                obj.userstatus = "ACTIVE"
            try:
                obj.save()
            except DataError:
                messages.error(request, "One or more values are longer than the allowed database limit.")
                form.add_error(None, "One or more values are longer than the allowed database limit.")
                records = model.objects.all().order_by(pk_name)
                entity_ui = _build_entity_ui_payload(entity, config, form, records, editing=None)
                return _render_core_react_page(request, config["active_page"], "entity", entity_ui)
            messages.success(request, f"{config['title'][:-1] if config['title'].endswith('s') else config['title']} created.")
            return redirect("core:entity_list", entity=entity)
    else:
        form = form_class()

    records = model.objects.all().order_by(pk_name)
    entity_ui = _build_entity_ui_payload(entity, config, form, records, editing=None)
    return _render_core_react_page(request, config["active_page"], "entity", entity_ui)


@superadmin_required
def entity_edit(request, entity, pk):
    if not _can_manage_entity(request.current_role, entity):
        messages.error(request, "You do not have permission to edit this module.")
        return redirect("core:dashboard_home")

    config = _entity_or_404(entity)
    model = config["model"]
    form_class = config["form"]
    pk_name = model._meta.pk.name
    obj = get_object_or_404(model, **{pk_name: pk})

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            try:
                form.save()
            except DataError:
                messages.error(request, "One or more values are longer than the allowed database limit.")
                form.add_error(None, "One or more values are longer than the allowed database limit.")
                records = model.objects.all().order_by(pk_name)
                entity_ui = _build_entity_ui_payload(entity, config, form, records, editing=obj)
                return _render_core_react_page(request, config["active_page"], "entity", entity_ui)
            messages.success(request, f"{config['title'][:-1] if config['title'].endswith('s') else config['title']} updated.")
            return redirect("core:entity_list", entity=entity)
    else:
        form = form_class(instance=obj)

    records = model.objects.all().order_by(pk_name)
    entity_ui = _build_entity_ui_payload(entity, config, form, records, editing=obj)
    return _render_core_react_page(request, config["active_page"], "entity", entity_ui)


@superadmin_required
def entity_delete(request, entity, pk):
    if not _can_manage_entity(request.current_role, entity):
        messages.error(request, "You do not have permission to delete in this module.")
        return redirect("core:dashboard_home")

    if request.method != "POST":
        return redirect("core:entity_list", entity=entity)
    config = _entity_or_404(entity)
    model = config["model"]
    pk_name = model._meta.pk.name
    obj = get_object_or_404(model, **{pk_name: pk})
    obj.delete()
    messages.success(request, f"{config['title'][:-1] if config['title'].endswith('s') else config['title']} deleted.")
    return redirect("core:entity_list", entity=entity)


@superadmin_required
def toggle_user_status(request, pk):
    if request.current_role != ROLE_SUPERADMIN:
        messages.error(request, "Only super admin can change user status.")
        return redirect("core:dashboard_home")

    if request.method != "POST":
        return redirect("core:entity_list", entity="users")
    user = get_object_or_404(TblUsers, userid=pk)
    user.userstatus = "INACTIVE" if (user.userstatus or "").upper() == "ACTIVE" else "ACTIVE"
    user.save(update_fields=["userstatus"])
    messages.success(request, f"User status changed to {user.userstatus}.")
    return redirect("core:entity_list", entity="users")


@superadmin_required
def request_list(request, filter_key="all", user_page_mode=None):
    if filter_key not in REQUEST_FILTER_LABELS:
        raise Http404("Unknown request filter.")

    can_request_create = request.current_permissions["can_request_create"]
    is_user_request_mode = request.current_role == ROLE_USER
    if is_user_request_mode:
        if user_page_mode is None:
            return redirect("core:request_my")
        if user_page_mode not in {"make", "my"}:
            user_page_mode = "my"
    else:
        if user_page_mode in {"make", "my"}:
            return redirect("core:request_list")
        user_page_mode = "admin"
    form_class = UserRequestForm if is_user_request_mode else RequestForm

    if request.method == "POST":
        if not can_request_create:
            messages.error(request, "You can view requests, but cannot create new ones.")
            if is_user_request_mode:
                return redirect("core:request_make")
            return redirect("core:request_list_filtered", filter_key=filter_key)
        form = form_class(request.POST, request.FILES, current_user=request.current_user)
        if form.is_valid():
            obj = form.save(commit=False)
            uploaded_reference = form.cleaned_data.get("reference_file") if "reference_file" in form.cleaned_data else None
            today = timezone.localdate()
            obj.requestdate = today
            if is_user_request_mode:
                obj.requestor = request.current_user.name
                obj.department = obj.department or request.current_user.userdepartment
                obj.personnel = "UNASSIGNED"
                obj.status = STATUS_PENDING_APPROVAL
                obj.notes = ""
                obj.dateupdated = today
                obj.verifieddate = today
                obj.verifiedby = ""
                obj.findings = ""
                obj.verifiednote = ""
            else:
                obj.dateupdated = today
                obj.verifieddate = today
                obj.verifiedby = ""
                obj.findings = ""
                obj.verifiednote = ""
                obj.status = obj.status or "NEW"
                obj.notes = obj.notes or ""
            obj.save()
            if is_user_request_mode and uploaded_reference:
                _save_request_reference_file(obj, uploaded_reference)
            messages.success(request, "Request created.")
            if is_user_request_mode:
                return redirect("core:request_make")
            return redirect("core:request_list_filtered", filter_key=filter_key)
    else:
        initial_data = {"status": STATUS_PENDING_APPROVAL}
        if is_user_request_mode:
            initial_data.update(
                {
                    "requestor": request.current_user.name,
                    "department": request.current_user.userdepartment,
                    "requestdept": request.current_user.userdepartment,
                    "dateupdated": timezone.localdate(),
                    "verifieddate": timezone.localdate(),
                }
            )
        form = form_class(initial=initial_data, current_user=request.current_user)

    all_records = list(TblRequest.objects.all().order_by("-requestno"))
    if is_user_request_mode:
        user_name = (request.current_user.name or "").strip().lower()
        user_login = (request.current_user.username or "").strip().lower()
        all_records = [
            record
            for record in all_records
            if (record.requestor or "").strip().lower() in {user_name, user_login}
        ]
    filtered_records = [record for record in all_records if _match_request_filter(record, filter_key)]

    query = request.GET.get("q", "").strip().lower()
    if query:
        def _matches(record):
            haystack = " ".join(
                [
                    str(record.requestno),
                    str(record.requestdate),
                    record.requestor or "",
                    record.department or "",
                    record.requestdept or "",
                    record.machinegroup or "",
                    record.worktype or "",
                    record.approval or "",
                    record.status or "",
                    record.personnel or "",
                    record.description or "",
                ]
            ).lower()
            return query in haystack

        filtered_records = [record for record in filtered_records if _matches(record)]

    counts = {
        "all": len([r for r in all_records if _match_request_filter(r, "all")]),
        "current": len([r for r in all_records if _match_request_filter(r, "current")]),
        "on_going": len([r for r in all_records if _match_request_filter(r, "on-going")]),
        "verification": len([r for r in all_records if _match_request_filter(r, "verification")]),
        "done": len([r for r in all_records if _match_request_filter(r, "done")]),
        "rejected": len([r for r in all_records if _match_request_filter(r, "rejected")]),
        "backjob": len([r for r in all_records if _match_request_filter(r, "backjob")]),
    }

    today_date = timezone.localdate()
    next_request_no = _next_pk(TblRequest) if is_user_request_mode else None
    request_ui = _build_request_ui_payload(
        request=request,
        filter_key=filter_key,
        form=form,
        records=filtered_records,
        counts=counts,
        query=request.GET.get("q", "").strip(),
        is_user_request_mode=is_user_request_mode,
        user_page_mode=user_page_mode,
        is_superadmin=request.current_role == ROLE_SUPERADMIN,
        today_date=today_date,
        next_request_no=next_request_no,
    )
    if is_user_request_mode:
        active_page = "myrequest" if user_page_mode == "my" else "makerequest"
    else:
        active_page = filter_key if filter_key != "all" else "allrequest"
    return _render_core_react_page(request, active_page, "requests", request_ui)


@superadmin_required
def request_action(request, pk, action):
    if not request.current_permissions["can_request_action"]:
        messages.error(request, "You do not have permission to update request status.")
        return redirect("core:request_list")

    if request.method != "POST":
        return redirect("core:request_list")

    request_obj = get_object_or_404(TblRequest, requestno=pk)
    current_status = str(request_obj.status or "").strip()
    current_role = request.current_role
    current_user = request.current_user
    can_manage_operations = bool(request.current_permissions.get("can_request_operations"))
    can_manage_approval = bool(request.current_permissions.get("can_request_approval"))
    can_edit_verification_fields = bool(request.current_permissions.get("can_request_verification_fields"))

    def _is_superadmin_actor():
        return current_role == ROLE_SUPERADMIN

    def _is_assigned_approver_actor():
        return _is_assigned_approver_for_request(current_user, request_obj)

    def _is_executor_head_actor():
        return _is_request_department_admin(current_user, current_role, request_obj)

    def _personnel_is_valid_for_requested_department(name):
        selected_name = str(name or "").strip()
        if not selected_name or selected_name.upper() == "UNASSIGNED":
            return False
        requested_department = str(request_obj.requestdept or "").strip().lower()
        allowed_personnel = set()
        for item in TblPersonnel.objects.only("personnelname", "personneldept"):
            dept = str(item.personneldept or "").strip().lower()
            personnel_name = str(item.personnelname or "").strip()
            if dept == requested_department and personnel_name:
                allowed_personnel.add(personnel_name.lower())
        return selected_name.lower() in allowed_personnel

    today = timezone.localdate()

    if action == "update":
        selected_update_scope = str(request.POST.get("update_scope", "all") or "all").strip().lower()
        if selected_update_scope not in {"all", "assignment", "verification"}:
            selected_update_scope = "all"
        is_assignment_scope = selected_update_scope in {"all", "assignment"}
        is_verification_scope = selected_update_scope in {"all", "verification"}

        if not (can_manage_operations or can_edit_verification_fields):
            messages.error(request, "You do not have permission to update this request.")
            return redirect("core:request_list")

        selected_personnel = str(request.POST.get("personnel", "") or "").strip()
        selected_status = str(request.POST.get("status", "") or "").strip()
        selected_notes = str(request.POST.get("notes", "") or "").strip()
        selected_findings = str(request.POST.get("findings", "") or "").strip()
        selected_verified_note = str(request.POST.get("verifiednote", "") or "").strip()
        selected_dateneeded = str(request.POST.get("dateneeded", "") or "").strip()

        if not can_edit_verification_fields and (selected_findings or selected_verified_note):
            messages.error(request, "Only admin or super admin can edit findings and verifier notes.")
            return redirect("core:request_list")

        if not selected_status:
            messages.error(request, "Status is required.")
            return redirect("core:request_list")

        target_status = _canonical_status(selected_status[:50])
        current_is_pending = _is_pending_approval_status(current_status)
        current_is_approved = _is_approved_status(current_status)
        current_is_on_going = _is_on_going_status(current_status)
        current_is_verification = _is_verification_status(current_status)
        current_is_back_job = _is_back_job_status(current_status)
        current_is_closed = _is_closed_status(current_status)
        current_is_rejected = _is_rejected_status(current_status)
        existing_personnel = str(request_obj.personnel or "").strip()
        existing_notes = str(request_obj.notes or "").strip()
        existing_schedule = str(request_obj.dateneeded or "").strip()
        pending_resolution_status = ""
        if current_is_pending:
            if _is_approved_status(selected_findings):
                pending_resolution_status = STATUS_APPROVED
            elif _is_rejected_status(selected_findings):
                pending_resolution_status = STATUS_REJECTED
            elif _is_approved_status(target_status):
                pending_resolution_status = STATUS_APPROVED
            elif _is_rejected_status(target_status):
                pending_resolution_status = STATUS_REJECTED
        force_superadmin_pending_assignment = (
            current_is_pending
            and is_assignment_scope
            and _is_superadmin_actor()
            and (_is_on_going_status(target_status) or _is_verification_status(target_status))
        )
        superadmin_findings_status = ""
        if _is_superadmin_actor() and selected_findings:
            mapped_superadmin_status = _canonical_status(selected_findings[:50])
            if mapped_superadmin_status in {
                STATUS_APPROVED,
                STATUS_ON_GOING,
                STATUS_FOR_VERIFICATION,
                STATUS_BACK_JOB,
                STATUS_CLOSED,
                STATUS_REJECTED,
            }:
                superadmin_findings_status = mapped_superadmin_status

        if not is_assignment_scope:
            if not can_edit_verification_fields:
                messages.error(request, "You do not have permission to update verification details.")
                return redirect("core:request_list")
            if current_is_closed or current_is_rejected:
                messages.error(request, "Closed or rejected requests can no longer be updated.")
                return redirect("core:request_list")
            if superadmin_findings_status:
                request_obj.status = superadmin_findings_status
                request_obj.findings = selected_findings[:50]
            elif current_is_pending:
                if not can_manage_approval:
                    messages.error(request, "Only admin or super admin can process this approval.")
                    return redirect("core:request_list")
                if not pending_resolution_status:
                    messages.error(request, "For pending approval, set Findings to APPROVED or REJECTED then Save Verification.")
                    return redirect("core:request_list")
                request_obj.status = pending_resolution_status
                request_obj.findings = "APPROVED" if _status_equals(request_obj.status, STATUS_APPROVED) else STATUS_REJECTED
            elif selected_findings:
                request_obj.findings = selected_findings[:50]
            request_obj.verifiednote = selected_verified_note[:100]
            request_obj.dateupdated = today
            if _status_equals(request_obj.status, STATUS_CLOSED):
                request_obj.verifiedby = str(current_user.name or "").strip()[:50]
                request_obj.verifieddate = today
            request_obj.save()
            messages.success(request, f"Request #{request_obj.requestno} updated.")
            return redirect("core:request_list")

        if not can_manage_operations:
            if selected_personnel and selected_personnel != existing_personnel:
                messages.error(request, "You do not have permission to edit personnel.")
                return redirect("core:request_list")
            if selected_dateneeded and selected_dateneeded != existing_schedule:
                messages.error(request, "You do not have permission to edit scheduled date.")
                return redirect("core:request_list")
            if selected_notes and selected_notes != existing_notes:
                messages.error(request, "You do not have permission to edit notes.")
                return redirect("core:request_list")
            if selected_status and not _status_equals(selected_status, current_status) and not (
                current_is_pending and can_manage_approval and pending_resolution_status
            ):
                messages.error(request, "You do not have permission to edit status.")
                return redirect("core:request_list")
            if not (current_is_pending and can_manage_approval):
                request_obj.dateupdated = today
                if can_edit_verification_fields:
                    if selected_findings:
                        request_obj.findings = selected_findings[:50]
                    request_obj.verifiednote = selected_verified_note[:100]
                request_obj.save()
                messages.success(request, f"Request #{request_obj.requestno} updated.")
                return redirect("core:request_list")

        effective_personnel = selected_personnel or existing_personnel
        effective_notes = selected_notes or existing_notes
        effective_schedule = selected_dateneeded or existing_schedule

        requires_complete_details = (
            current_is_approved
            or current_is_back_job
            or current_is_on_going
            or current_is_verification
            or force_superadmin_pending_assignment
            or (
                not current_is_pending
                and (
                    _is_on_going_status(target_status)
                    or _is_verification_status(target_status)
                    or _is_back_job_status(target_status)
                    or _is_closed_status(target_status)
                    or _is_rejected_status(target_status)
                )
            )
        )

        if current_is_closed or current_is_rejected:
            messages.error(request, "Closed or rejected requests can no longer be updated.")
            return redirect("core:request_list")

        if current_is_pending and can_manage_operations and not can_manage_approval:
            messages.error(request, "Admin or super admin must approve this request before personnel assignment.")
            return redirect("core:request_list")

        if current_is_pending and is_assignment_scope and not force_superadmin_pending_assignment:
            messages.error(request, "Pending approval requests cannot be assigned yet.")
            return redirect("core:request_list")

        if requires_complete_details:
            if not _personnel_is_valid_for_requested_department(effective_personnel):
                messages.error(request, "Please assign personnel first before saving status.")
                return redirect("core:request_list")
            if not effective_schedule:
                messages.error(request, "Please set the scheduled date first before saving status.")
                return redirect("core:request_list")
            if not effective_notes:
                messages.error(request, "Please fill out the work details in Notes before saving status.")
                return redirect("core:request_list")

        if current_is_pending:
            if force_superadmin_pending_assignment:
                try:
                    request_obj.dateneeded = date.fromisoformat(effective_schedule)
                except ValueError:
                    messages.error(request, "Scheduled date is invalid.")
                    return redirect("core:request_list")
                request_obj.personnel = effective_personnel[:50]
                if _is_verification_status(target_status):
                    request_obj.status = STATUS_FOR_VERIFICATION
                    request_obj.findings = STATUS_FOR_VERIFICATION
                else:
                    request_obj.status = STATUS_ON_GOING
                    request_obj.findings = STATUS_ON_GOING
            else:
                if not can_manage_approval:
                    messages.error(request, "Only admin or super admin can process this approval.")
                    return redirect("core:request_list")
                if not pending_resolution_status:
                    messages.error(request, "For pending approval, set Findings to APPROVED or REJECTED then Save Status.")
                    return redirect("core:request_list")
                request_obj.status = pending_resolution_status
                request_obj.findings = "APPROVED" if _status_equals(request_obj.status, STATUS_APPROVED) else STATUS_REJECTED
        elif current_is_approved or current_is_back_job:
            if not (_is_superadmin_actor() or _is_executor_head_actor() or _is_assigned_approver_actor()):
                messages.error(request, "Only admin/super admin or the assigned approver can assign and schedule this work.")
                return redirect("core:request_list")
            if not (_status_equals(target_status, STATUS_ON_GOING) or _status_equals(target_status, current_status)):
                messages.error(request, "Approved or back job requests can only move to ON GOING.")
                return redirect("core:request_list")
            if not _personnel_is_valid_for_requested_department(effective_personnel):
                messages.error(request, "Assigned personnel is required and must belong to the requested department.")
                return redirect("core:request_list")
            if not effective_schedule:
                messages.error(request, "Scheduled date is required before saving this work request.")
                return redirect("core:request_list")
            if not effective_notes:
                messages.error(request, "Please complete the work details in Notes before saving.")
                return redirect("core:request_list")
            try:
                request_obj.dateneeded = date.fromisoformat(effective_schedule)
            except ValueError:
                messages.error(request, "Scheduled date is invalid.")
                return redirect("core:request_list")
            request_obj.personnel = effective_personnel[:50]
            if _status_equals(target_status, STATUS_ON_GOING):
                request_obj.status = STATUS_ON_GOING
                request_obj.findings = STATUS_ON_GOING
        elif current_is_on_going:
            if not (_is_superadmin_actor() or _is_executor_head_actor() or _is_assigned_approver_actor()):
                messages.error(request, "Only admin/super admin or the assigned approver can update this on-going request.")
                return redirect("core:request_list")
            if not (_status_equals(target_status, STATUS_ON_GOING) or _status_equals(target_status, STATUS_FOR_VERIFICATION)):
                messages.error(request, "On-going requests can only stay ON GOING or move to FOR VERIFICATION.")
                return redirect("core:request_list")
            if not _personnel_is_valid_for_requested_department(effective_personnel):
                messages.error(request, "A valid assigned personnel is required.")
                return redirect("core:request_list")
            if not effective_schedule:
                messages.error(request, "Scheduled date is required before saving this work request.")
                return redirect("core:request_list")
            if not effective_notes:
                messages.error(request, "Please complete the work details in Notes before saving.")
                return redirect("core:request_list")
            try:
                request_obj.dateneeded = date.fromisoformat(effective_schedule)
            except ValueError:
                messages.error(request, "Scheduled date is invalid.")
                return redirect("core:request_list")
            request_obj.personnel = effective_personnel[:50]
            if _status_equals(target_status, STATUS_FOR_VERIFICATION):
                request_obj.status = STATUS_FOR_VERIFICATION
                request_obj.findings = STATUS_FOR_VERIFICATION
            else:
                request_obj.status = STATUS_ON_GOING
                request_obj.findings = STATUS_ON_GOING
        elif current_is_verification:
            if not can_manage_approval:
                messages.error(request, "Only admin or super admin can close this verification request.")
                return redirect("core:request_list")
            if not (_status_equals(target_status, STATUS_FOR_VERIFICATION) or _status_equals(target_status, STATUS_CLOSED)):
                messages.error(request, "Verification stage can only stay FOR VERIFICATION or be closed by admin/super admin.")
                return redirect("core:request_list")
            if not _personnel_is_valid_for_requested_department(effective_personnel):
                messages.error(request, "Assigned personnel is required before saving this verification request.")
                return redirect("core:request_list")
            if not effective_schedule:
                messages.error(request, "Scheduled date is required before saving this verification request.")
                return redirect("core:request_list")
            if not effective_notes:
                messages.error(request, "Please complete the work details in Notes before saving.")
                return redirect("core:request_list")
            try:
                request_obj.dateneeded = date.fromisoformat(effective_schedule)
            except ValueError:
                messages.error(request, "Scheduled date is invalid.")
                return redirect("core:request_list")
            request_obj.personnel = effective_personnel[:50]
            request_obj.status = STATUS_CLOSED if _status_equals(target_status, STATUS_CLOSED) else STATUS_FOR_VERIFICATION
            if _status_equals(request_obj.status, STATUS_CLOSED):
                request_obj.findings = STATUS_CLOSED
        else:
            messages.error(request, "Unsupported request status transition.")
            return redirect("core:request_list")

        # Free-form notes can still be updated within the allowed stage transition.
        request_obj.notes = selected_notes[:200]
        if can_edit_verification_fields and is_verification_scope:
            if selected_findings and not request_obj.findings:
                request_obj.findings = selected_findings[:50]
            request_obj.verifiednote = selected_verified_note[:100]
        request_obj.dateupdated = today
        if can_edit_verification_fields and _status_equals(request_obj.status, STATUS_CLOSED):
            request_obj.verifiedby = str(current_user.name or "").strip()[:50]
            request_obj.verifieddate = today
        request_obj.save()
        messages.success(request, f"Request #{request_obj.requestno} updated.")
        return redirect("core:request_list")

    if action == "approve":
        if not _is_pending_approval_status(current_status):
            messages.error(request, "Only pending approval requests can be approved.")
            return redirect("core:request_list")
        if not can_manage_approval:
            messages.error(request, "Only admin or super admin can approve this request.")
            return redirect("core:request_list")
        request_obj.status = STATUS_APPROVED
        request_obj.findings = "APPROVED"
        request_obj.dateupdated = today
        request_obj.save(update_fields=["status", "findings", "dateupdated"])
        messages.success(request, f"Request #{request_obj.requestno} approved.")
        return redirect("core:request_list")

    if action == "reject":
        if not _is_pending_approval_status(current_status):
            messages.error(request, "Only pending approval requests can be rejected.")
            return redirect("core:request_list")
        if not can_manage_approval:
            messages.error(request, "Only admin or super admin can reject this request.")
            return redirect("core:request_list")
        request_obj.status = STATUS_REJECTED
        request_obj.findings = STATUS_REJECTED
        request_obj.dateupdated = today
        request_obj.save(update_fields=["status", "findings", "dateupdated"])
        messages.success(request, f"Request #{request_obj.requestno} rejected.")
        return redirect("core:request_list")

    raise Http404("Unsupported action.")


@superadmin_required
def request_user_verify(request, pk):
    if request.method != "POST":
        return redirect("core:request_my")
    if request.current_role != ROLE_USER:
        messages.error(request, "Only requestors can verify their requests.")
        return redirect("core:request_list")

    request_obj = get_object_or_404(TblRequest, requestno=pk)
    current_name = (request.current_user.name or "").strip().lower()
    current_login = (request.current_user.username or "").strip().lower()
    owner_name = (request_obj.requestor or "").strip().lower()
    if owner_name not in {current_name, current_login}:
        messages.error(request, "You can only verify your own request.")
        return redirect("core:request_my")

    if _status_category(request_obj.status) != "verification":
        messages.error(request, "Only requests under FOR VERIFICATION can be marked as closed.")
        return redirect("core:request_my")

    today = timezone.localdate()
    request_obj.status = STATUS_CLOSED
    request_obj.findings = "VERIFIED"
    request_obj.verifiedby = str(request.current_user.name or request.current_user.username or "").strip()[:50]
    request_obj.verifieddate = today
    request_obj.dateupdated = today
    request_obj.save(update_fields=["status", "findings", "verifiedby", "verifieddate", "dateupdated"])
    messages.success(request, f"Request #{request_obj.requestno} verified and marked as CLOSED.")
    return redirect("core:request_my")


@superadmin_required
def request_user_backjob(request, pk):
    if request.method != "POST":
        return redirect("core:request_my")
    if request.current_role != ROLE_USER:
        messages.error(request, "Only requestors can submit back job requests.")
        return redirect("core:request_list")

    request_obj = get_object_or_404(TblRequest, requestno=pk)
    current_name = (request.current_user.name or "").strip().lower()
    current_login = (request.current_user.username or "").strip().lower()
    owner_name = (request_obj.requestor or "").strip().lower()
    if owner_name not in {current_name, current_login}:
        messages.error(request, "You can only update your own request.")
        return redirect("core:request_my")

    if _status_category(request_obj.status) != "verification":
        messages.error(request, "Only requests under FOR VERIFICATION can be returned as BACK JOB.")
        return redirect("core:request_my")

    today = timezone.localdate()
    request_obj.status = STATUS_BACK_JOB
    request_obj.findings = STATUS_BACK_JOB
    request_obj.verifiedby = str(request.current_user.name or request.current_user.username or "").strip()[:50]
    request_obj.verifieddate = today
    request_obj.dateupdated = today
    request_obj.save(update_fields=["status", "findings", "verifiedby", "verifieddate", "dateupdated"])
    messages.success(request, f"Request #{request_obj.requestno} returned as BACK JOB.")
    return redirect("core:request_my")


@superadmin_required
def request_reference_file(request, pk):
    if not request.current_permissions.get("can_request_action"):
        raise Http404("Not found.")

    request_obj = get_object_or_404(TblRequest, requestno=pk)
    reference = get_object_or_404(TblRequestReference, requestno=request_obj.requestno)
    raw = bytes(reference.filedata or b"")
    if not raw:
        raise Http404("No file found.")

    content_type = str(reference.contenttype or "").strip() or "application/octet-stream"
    filename = str(reference.filename or f"request-{request_obj.requestno}-reference").strip() or f"request-{request_obj.requestno}-reference"
    response = HttpResponse(raw, content_type=content_type)
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
    return response


@superadmin_required
def request_delete(request, pk):
    if not request.current_permissions["can_request_delete"]:
        messages.error(request, "Only super admin can delete requests.")
        return redirect("core:request_list")

    if request.method != "POST":
        return redirect("core:request_list")
    request_obj = get_object_or_404(TblRequest, requestno=pk)
    TblRequestReference.objects.filter(requestno=request_obj.requestno).delete()
    request_obj.delete()
    messages.success(request, f"Request #{pk} deleted.")
    return redirect("core:request_list")

# Create your views here.
