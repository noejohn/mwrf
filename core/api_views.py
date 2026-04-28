import json

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .forms import ChangePasswordForm, UserProfileForm
from .models import TblRequest, TblUsers
from .security import hash_password, verify_user_password
from .views import (
    ENTITY_CONFIG,
    REQUEST_FILTER_LABELS,
    ROLE_SUPERADMIN,
    _build_dashboard_ui_payload,
    _build_entity_ui_payload,
    _build_permissions,
    _build_profile_ui_payload,
    _build_request_ui_payload,
    _can_manage_entity,
    _ensure_default_admin_user,
    _match_request_filter,
    _next_pk,
    _resolve_role,
)


def _token_response_for_user(user):
    role = _resolve_role(user.userposition)
    refresh = RefreshToken()
    refresh["user_id"] = str(user.userid)
    refresh["username"] = str(user.username or "")
    refresh["name"] = str(user.name or "")
    refresh["role"] = role
    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
        "token_type": "Bearer",
        "expires_in": int(access.lifetime.total_seconds()),
        "user": {
            "userid": user.userid,
            "name": user.name or "",
            "username": user.username or "",
            "role": role,
            "role_label": user.userposition or "",
            "status": user.userstatus or "",
            "department": user.userdepartment or "",
        },
    }


def _auth_context_for_user(user):
    role = _resolve_role(user.userposition)
    return {
        "role": role,
        "permissions": _build_permissions(role),
    }


class ApiLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", "")).strip()

        if not username or not password:
            return Response({"ok": False, "message": "Username and password are required."}, status=400)

        _ensure_default_admin_user()
        user = TblUsers.objects.filter(username__iexact=username).first()
        if not user or not verify_user_password(user, password):
            return Response({"ok": False, "message": "Invalid username or password."}, status=401)
        if (user.userstatus or "").upper() != "ACTIVE":
            return Response({"ok": False, "message": "This user is inactive."}, status=403)

        return Response({"ok": True, **_token_response_for_user(user)})


class ApiRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        fullname = str(request.data.get("fullname", "")).strip()
        department = str(request.data.get("department", "")).strip()
        address = str(request.data.get("address", "")).strip()
        contact = str(request.data.get("contact", "")).strip()
        password = str(request.data.get("password", ""))
        consent = bool(request.data.get("consent", False))

        if not fullname or not department or not address or not contact or not password:
            return Response({"ok": False, "message": "All fields are required."}, status=400)
        if len(fullname) > 50 or len(department) > 50 or len(address) > 25 or len(contact) > 15 or len(password) > 50:
            return Response({"ok": False, "message": "One or more fields exceed allowed length."}, status=400)
        if len(password) < 6:
            return Response({"ok": False, "message": "Password must be at least 6 characters."}, status=400)
        if not consent:
            return Response({"ok": False, "message": "You must accept the data privacy consent."}, status=400)

        dep_exists = ENTITY_CONFIG["departments"]["model"].objects.filter(depname__iexact=department).exists()
        if not dep_exists:
            return Response({"ok": False, "message": "Selected department does not exist."}, status=400)

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
        return Response(
            {
                "ok": True,
                "message": "Registration submitted. Wait for super admin activation.",
                "username": username,
            },
            status=201,
        )


class ApiMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        auth_ctx = _auth_context_for_user(user)
        return Response(
            {
                "ok": True,
                "user": {
                    "userid": user.userid,
                    "name": user.name or "",
                    "username": user.username or "",
                    "role": auth_ctx["role"],
                    "role_label": user.userposition or "",
                    "status": user.userstatus or "",
                    "department": user.userdepartment or "",
                },
                "permissions": auth_ctx["permissions"],
            }
        )


class ApiDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        auth_ctx = _auth_context_for_user(user)
        if auth_ctx["role"] == "user":
            return Response({"ok": False, "message": "Users should open requests view."}, status=403)

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
        from .views import _status_category

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
        return Response({"ok": True, "data": _build_dashboard_ui_payload(requests_qs, counts, status_rows)})


class ApiEntityView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_payload(self, user, entity, form, editing_obj=None):
        config = ENTITY_CONFIG.get(entity)
        model = config["model"]
        pk_name = model._meta.pk.name
        records = model.objects.all().order_by(pk_name)
        return _build_entity_ui_payload(entity, config, form, records, editing_obj)

    def get(self, request, entity, pk=None):
        auth_ctx = _auth_context_for_user(request.user)
        if not _can_manage_entity(auth_ctx["role"], entity):
            return Response({"ok": False, "message": "You do not have permission to manage this module."}, status=403)

        config = ENTITY_CONFIG.get(entity)
        if not config:
            return Response({"ok": False, "message": "Entity not found."}, status=404)
        model = config["model"]
        form_class = config["form"]
        if pk is not None:
            obj = get_object_or_404(model, **{model._meta.pk.name: pk})
            form = form_class(instance=obj)
            payload = self._get_payload(request.user, entity, form, obj)
        else:
            form = form_class()
            payload = self._get_payload(request.user, entity, form, None)
        return Response({"ok": True, "data": payload})

    def post(self, request, entity, pk=None):
        auth_ctx = _auth_context_for_user(request.user)
        if not _can_manage_entity(auth_ctx["role"], entity):
            return Response({"ok": False, "message": "You do not have permission to manage this module."}, status=403)

        config = ENTITY_CONFIG.get(entity)
        if not config:
            return Response({"ok": False, "message": "Entity not found."}, status=404)

        model = config["model"]
        form_class = config["form"]
        pk_name = model._meta.pk.name
        editing_obj = None
        if pk is not None:
            editing_obj = get_object_or_404(model, **{pk_name: pk})
            form = form_class(request.data, request.FILES, instance=editing_obj)
        else:
            form = form_class(request.data, request.FILES)

        if form.is_valid():
            obj = form.save(commit=False)
            if not pk and config.get("manual_pk"):
                setattr(obj, pk_name, _next_pk(model))
            if entity == "users" and not obj.userstatus:
                obj.userstatus = "ACTIVE"
            obj.save()
            fresh_form = form_class()
            return Response({"ok": True, "data": self._get_payload(request.user, entity, fresh_form, None)})

        status_code = status.HTTP_400_BAD_REQUEST
        return Response({"ok": False, "data": self._get_payload(request.user, entity, form, editing_obj)}, status=status_code)

    def delete(self, request, entity, pk):
        auth_ctx = _auth_context_for_user(request.user)
        if not _can_manage_entity(auth_ctx["role"], entity):
            return Response({"ok": False, "message": "You do not have permission to delete in this module."}, status=403)

        config = ENTITY_CONFIG.get(entity)
        if not config:
            return Response({"ok": False, "message": "Entity not found."}, status=404)
        model = config["model"]
        obj = get_object_or_404(model, **{model._meta.pk.name: pk})
        obj.delete()
        form_class = config["form"]
        return Response({"ok": True, "data": self._get_payload(request.user, entity, form_class(), None)})


class ApiToggleUserStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        auth_ctx = _auth_context_for_user(request.user)
        if auth_ctx["role"] != ROLE_SUPERADMIN:
            return Response({"ok": False, "message": "Only super admin can change user status."}, status=403)
        user = get_object_or_404(TblUsers, userid=pk)
        user.userstatus = "INACTIVE" if (user.userstatus or "").upper() == "ACTIVE" else "ACTIVE"
        user.save(update_fields=["userstatus"])
        return Response({"ok": True, "status": user.userstatus})


class ApiRequestsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, filter_key="all"):
        if filter_key not in REQUEST_FILTER_LABELS:
            return Response({"ok": False, "message": "Unknown request filter."}, status=404)
        user = request.user
        auth_ctx = _auth_context_for_user(user)
        permissions = auth_ctx["permissions"]
        is_user_request_mode = auth_ctx["role"] == "user"
        from .forms import RequestForm, UserRequestForm

        form_class = UserRequestForm if is_user_request_mode else RequestForm
        initial_data = {"status": "NEW"}
        if is_user_request_mode:
            initial_data.update(
                {
                    "requestor": user.name,
                    "department": user.userdepartment,
                    "dateupdated": timezone.localdate(),
                    "verifieddate": timezone.localdate(),
                }
            )
        form = form_class(initial=initial_data, current_user=user)

        all_records = list(TblRequest.objects.all().order_by("-requestno"))
        if is_user_request_mode:
            user_name = (user.name or "").strip().lower()
            user_login = (user.username or "").strip().lower()
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
        payload = _build_request_ui_payload(
            request=type("ReqCtx", (), {"current_permissions": permissions})(),
            filter_key=filter_key,
            form=form,
            records=filtered_records,
            counts=counts,
            query=request.GET.get("q", "").strip(),
            is_user_request_mode=is_user_request_mode,
            is_superadmin=auth_ctx["role"] == ROLE_SUPERADMIN,
            today_date=timezone.localdate(),
            next_request_no=_next_pk(TblRequest) if is_user_request_mode else None,
        )
        return Response({"ok": True, "data": payload})

    def post(self, request, filter_key="all"):
        if filter_key not in REQUEST_FILTER_LABELS:
            return Response({"ok": False, "message": "Unknown request filter."}, status=404)
        user = request.user
        auth_ctx = _auth_context_for_user(user)
        permissions = auth_ctx["permissions"]
        if not permissions.get("can_request_create"):
            return Response({"ok": False, "message": "You can view requests, but cannot create new ones."}, status=403)

        is_user_request_mode = auth_ctx["role"] == "user"
        from .forms import RequestForm, UserRequestForm

        form_class = UserRequestForm if is_user_request_mode else RequestForm
        form = form_class(request.data, request.FILES, current_user=user)
        if not form.is_valid():
            return Response({"ok": False, "errors": form.errors}, status=400)

        obj = form.save(commit=False)
        today = timezone.localdate()
        obj.requestdate = today
        if is_user_request_mode:
            obj.requestor = user.name
            obj.department = obj.department or user.userdepartment
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
        return self.get(request, filter_key=filter_key)


class ApiRequestActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, action):
        user = request.user
        auth_ctx = _auth_context_for_user(user)
        if not auth_ctx["permissions"].get("can_request_action"):
            return Response({"ok": False, "message": "You do not have permission to update request status."}, status=403)
        request_obj = get_object_or_404(TblRequest, requestno=pk)
        action_map = {
            "verify": "DONE",
            "reject": "REJECTED",
            "backjob": "BACK JOB",
        }
        target_status = action_map.get(action)
        if not target_status:
            return Response({"ok": False, "message": "Unsupported action."}, status=404)
        note = str(request.data.get("note", "")).strip()
        today = timezone.localdate()
        request_obj.status = target_status
        request_obj.dateupdated = today
        request_obj.verifiedby = user.name
        request_obj.verifieddate = today
        if note:
            request_obj.verifiednote = note[:100]
        request_obj.save()
        return Response({"ok": True, "status": target_status, "requestno": request_obj.requestno})


class ApiRequestDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        user = request.user
        auth_ctx = _auth_context_for_user(user)
        if not auth_ctx["permissions"].get("can_request_delete"):
            return Response({"ok": False, "message": "Only super admin can delete requests."}, status=403)
        request_obj = get_object_or_404(TblRequest, requestno=pk)
        request_obj.delete()
        return Response({"ok": True, "requestno": pk})


class ApiProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        user = TblUsers.objects.get(userid=request.user.userid)
        profile_form = UserProfileForm(instance=user)
        password_form = ChangePasswordForm(user=user)
        return Response({"ok": True, "data": _build_profile_ui_payload(user, profile_form, password_form)})

    def post(self, request):
        user = TblUsers.objects.get(userid=request.user.userid)
        action = str(request.data.get("action", "")).strip().lower()
        if action == "profile":
            profile_form = UserProfileForm(request.data, request.FILES, instance=user)
            password_form = ChangePasswordForm(user=user)
            if profile_form.is_valid():
                profile_form.save()
                return Response({"ok": True, "data": _build_profile_ui_payload(user, UserProfileForm(instance=user), password_form)})
            return Response({"ok": False, "data": _build_profile_ui_payload(user, profile_form, password_form)}, status=400)
        if action == "password":
            profile_form = UserProfileForm(instance=user)
            password_form = ChangePasswordForm(request.data, user=user)
            if password_form.is_valid():
                from .security import set_user_password
                set_user_password(user, password_form.cleaned_data["new_password"], save=True)
                return Response({"ok": True, "data": _build_profile_ui_payload(user, profile_form, ChangePasswordForm(user=user))})
            return Response({"ok": False, "data": _build_profile_ui_payload(user, profile_form, password_form)}, status=400)
        return Response({"ok": False, "message": "Unknown profile action."}, status=400)


class ApiTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
