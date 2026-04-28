import json
import base64
import imghdr
from functools import wraps

from django.contrib import messages
from django.db.models import Max
from django.http import Http404, JsonResponse
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
        "table_columns": ["approvalno", "approvalname"],
        "column_labels": {
            "approvalno": "No.",
            "approvalname": "Full Name",
        },
        "manual_pk": True,
    },
}

REQUEST_FILTER_LABELS = {
    "all": "All Machine Request",
    "current": "Current Machine Request",
    "on-going": "On going machine request",
    "verification": "Verification Requests",
    "done": "Done machine work request",
    "rejected": "Rejected machine request",
    "backjob": "Backjob machine request",
}

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


def _status_category(value):
    normalized = _normalize_status(value)
    if "reject" in normalized:
        return "rejected"
    if "back" in normalized and "job" in normalized:
        return "backjob"
    if "verify" in normalized:
        return "verification"
    if "ongoing" in normalized:
        return "on-going"
    if "done" in normalized or "complete" in normalized:
        return "done"
    if normalized == "new" or not normalized:
        return "new"
    return "other"


def _match_request_filter(request_obj, filter_key):
    category = _status_category(request_obj.status)
    if filter_key == "all":
        return True
    if filter_key == "current":
        return category in {"new", "on-going", "verification", "backjob"}
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


def _build_permissions(role):
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
        "can_request_action": role in {ROLE_SUPERADMIN, ROLE_ADMIN},
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
        request.current_permissions = _build_permissions(role)
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
        ("New", counts["new"]),
        ("On-going", counts["on_going"]),
        ("Verification", counts["verification"]),
        ("Done", counts["done"]),
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
        request_items.append(
            {
                "key": "allrequest",
                "label": "All Request",
                "url": reverse("core:request_list"),
            }
        )
        if permissions.get("can_request_action"):
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
                        "label": "Done",
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

    return {
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


def _build_request_ui_payload(
    request,
    filter_key,
    form,
    records,
    counts,
    query,
    is_user_request_mode,
    is_superadmin,
    today_date,
    next_request_no,
):
    def _string(value, default="-"):
        text = str(value or "").strip()
        return text if text else default

    def _serialize_request(req, index):
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
            "verifiedby": _string(req.verifiedby),
            "findings": _string(req.findings),
            "verifiednote": _string(req.verifiednote),
            "verifieddate": _string(req.verifieddate),
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

    return {
        "filterKey": filter_key,
        "filterLabel": REQUEST_FILTER_LABELS[filter_key],
        "query": query,
        "counts": counts,
        "isUserRequestMode": is_user_request_mode,
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
        "permissions": {
            "canRequestCreate": bool(request.current_permissions.get("can_request_create")),
            "canRequestAction": bool(request.current_permissions.get("can_request_action")),
            "canRequestDelete": bool(request.current_permissions.get("can_request_delete")),
        },
        "urls": {
            "allRequests": reverse("core:request_list"),
            "onGoingFilter": reverse("core:request_list_filtered", kwargs={"filter_key": "on-going"}),
            "verifyTemplate": reverse("core:request_action", kwargs={"pk": 0, "action": "verify"}),
            "rejectTemplate": reverse("core:request_action", kwargs={"pk": 0, "action": "reject"}),
            "backjobTemplate": reverse("core:request_action", kwargs={"pk": 0, "action": "backjob"}),
            "deleteTemplate": reverse("core:request_delete", kwargs={"pk": 0}),
        },
    }


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
            obj.save()
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
            form.save()
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
def request_list(request, filter_key="all"):
    if filter_key not in REQUEST_FILTER_LABELS:
        raise Http404("Unknown request filter.")

    can_request_create = request.current_permissions["can_request_create"]
    is_user_request_mode = request.current_role == ROLE_USER
    form_class = UserRequestForm if is_user_request_mode else RequestForm

    if request.method == "POST":
        if not can_request_create:
            messages.error(request, "You can view requests, but cannot create new ones.")
            return redirect("core:request_list_filtered", filter_key=filter_key)
        form = form_class(request.POST, request.FILES, current_user=request.current_user)
        if form.is_valid():
            obj = form.save(commit=False)
            today = timezone.localdate()
            obj.requestdate = today
            if is_user_request_mode:
                obj.requestor = request.current_user.name
                obj.department = obj.department or request.current_user.userdepartment
                obj.personnel = obj.personnel or "UNASSIGNED"
                obj.status = obj.status or "NEW"
                obj.notes = obj.notes or ""
                obj.dateupdated = obj.dateupdated or today
                obj.verifieddate = obj.verifieddate or today
                obj.verifiedby = obj.verifiedby or ""
                obj.findings = obj.findings or ""
                obj.verifiednote = obj.verifiednote or ""
            else:
                obj.dateupdated = today
                obj.verifieddate = today
                obj.verifiedby = ""
                obj.findings = ""
                obj.verifiednote = ""
                obj.status = obj.status or "NEW"
                obj.notes = obj.notes or ""
            obj.save()
            messages.success(request, "Request created.")
            return redirect("core:request_list_filtered", filter_key=filter_key)
    else:
        initial_data = {"status": "NEW"}
        if is_user_request_mode:
            initial_data.update(
                {
                    "requestor": request.current_user.name,
                    "department": request.current_user.userdepartment,
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
        "all": len(all_records),
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
        is_superadmin=request.current_role == ROLE_SUPERADMIN,
        today_date=today_date,
        next_request_no=next_request_no,
    )
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
    action_map = {
        "verify": "DONE",
        "reject": "REJECTED",
        "backjob": "BACK JOB",
    }
    target_status = action_map.get(action)
    if not target_status:
        raise Http404("Unsupported action.")

    note = request.POST.get("note", "").strip()
    today = timezone.localdate()
    request_obj.status = target_status
    request_obj.dateupdated = today
    request_obj.verifiedby = request.current_user.name
    request_obj.verifieddate = today
    if note:
        request_obj.verifiednote = note[:100]
    request_obj.save()
    messages.success(request, f"Request #{request_obj.requestno} marked as {target_status}.")
    return redirect("core:request_list")


@superadmin_required
def request_delete(request, pk):
    if not request.current_permissions["can_request_delete"]:
        messages.error(request, "Only super admin can delete requests.")
        return redirect("core:request_list")

    if request.method != "POST":
        return redirect("core:request_list")
    request_obj = get_object_or_404(TblRequest, requestno=pk)
    request_obj.delete()
    messages.success(request, f"Request #{pk} deleted.")
    return redirect("core:request_list")

# Create your views here.
