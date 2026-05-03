from django import forms

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
from .security import hash_password, verify_user_password

STATUS_PENDING_APPROVAL = "PENDING APPROVAL"


def _is_admin_position(value):
    normalized = "".join(ch for ch in str(value or "").lower() if ch.isalnum())
    if "super" in normalized and "admin" in normalized:
        return True
    return "admin" in normalized


def _is_superadmin_position(value):
    normalized = "".join(ch for ch in str(value or "").lower() if ch.isalnum())
    return "super" in normalized and "admin" in normalized


def _active_admin_choices(selected_department=""):
    selected_department_text = str(selected_department or "").strip().lower()
    choices = []
    seen = set()
    users = TblUsers.objects.order_by("name").only("name", "userdepartment", "userposition", "userstatus")

    for item in users:
        if not _is_admin_position(item.userposition):
            continue
        if str(item.userstatus or "").strip().upper() != "ACTIVE":
            continue
        name = str(item.name or "").strip()
        if not name:
            continue
        department = str(item.userdepartment or "").strip().lower()
        if selected_department_text and department != selected_department_text:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        choices.append((name, name))
    return choices


class BaseStyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class UserForm(BaseStyledModelForm):
    image_file = forms.FileField(required=False)
    confirm_password = forms.CharField(
        required=False,
        label="Confirm Password",
        widget=forms.PasswordInput(render_value=True),
    )

    class Meta:
        model = TblUsers
        fields = [
            "name",
            "userdepartment",
            "useraddress",
            "usercontact",
            "userposition",
            "username",
            "userpassword",
            "userstatus",
        ]
        widgets = {
            "userpassword": forms.PasswordInput(render_value=True),
            "userposition": forms.Select(
                choices=(
                    ("USER", "USER"),
                    ("ADMIN", "ADMIN"),
                    ("SUPER ADMIN", "SUPERADMIN"),
                )
            ),
            "userstatus": forms.Select(
                choices=(
                    ("ACTIVE", "ACTIVE"),
                    ("INACTIVE", "INACTIVE"),
                )
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dept_choices = [("", "Select Department")] + [
            (name, name) for name in TblDepartment.objects.order_by("depname").values_list("depname", flat=True)
        ]
        current_department = str(getattr(self.instance, "userdepartment", "") or "").strip()
        if current_department and all(current_department != value for value, _ in dept_choices):
            dept_choices.append((current_department, current_department))
        self.fields["userdepartment"] = forms.ChoiceField(
            choices=dept_choices,
            required=True,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        self.fields["userdepartment"].label = "Department"
        self.fields["useraddress"].label = "Address"
        self.fields["usercontact"].label = "Contact"
        self.fields["userposition"].label = "Role"
        self.fields["userpassword"].label = "Password"
        self.order_fields(
            [
                "name",
                "userdepartment",
                "useraddress",
                "usercontact",
                "userposition",
                "username",
                "userpassword",
                "confirm_password",
                "userstatus",
                "image_file",
            ]
        )
        current_value = str(getattr(self.instance, "userposition", "") or "").strip().upper().replace("-", " ")
        if current_value == "SUPERADMIN":
            current_value = "SUPER ADMIN"
        if current_value == "ADMINISTRATOR":
            current_value = "ADMIN"
        if current_value not in {"USER", "ADMIN", "SUPER ADMIN"}:
            current_value = "USER"
        self.initial.setdefault("userposition", current_value)

    def clean_username(self):
        username = str(self.cleaned_data.get("username", "")).strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        exists = TblUsers.objects.filter(username__iexact=username).exclude(userid=self.instance.userid).exists()
        if exists:
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password = str(cleaned.get("userpassword", ""))
        confirm_password = str(cleaned.get("confirm_password", ""))
        is_create = not bool(self.instance and self.instance.pk)
        previous_password = str(getattr(self.instance, "userpassword", "") or "")

        if is_create and not password:
            self.add_error("userpassword", "Password is required.")
        if password and len(password) < 6:
            self.add_error("userpassword", "Password must be at least 6 characters.")
        if password and len(password) > 50:
            self.add_error("userpassword", "Password must be at most 50 characters.")

        password_changed = bool(password and password != previous_password)
        if is_create or password_changed:
            if not confirm_password:
                self.add_error("confirm_password", "Please confirm the password.")
            elif password != confirm_password:
                self.add_error("confirm_password", "Passwords do not match.")
        elif confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_password = str(self.cleaned_data.get("userpassword", "") or "")
        previous_password = str(getattr(self.instance, "userpassword", "") or "")
        password_changed = bool(raw_password and raw_password != previous_password)
        if password_changed:
            instance.userpassword = hash_password(raw_password)
        uploaded = self.cleaned_data.get("image_file")
        if uploaded:
            instance.userimage = uploaded.read()
        elif not instance.userimage:
            instance.userimage = b""
        if commit:
            instance.save()
        return instance


class DepartmentForm(BaseStyledModelForm):
    class Meta:
        model = TblDepartment
        fields = ["depname"]
        labels = {
            "depname": "Department",
        }


class MachineForm(BaseStyledModelForm):
    class Meta:
        model = TblMachineGroup
        fields = ["machinename"]
        labels = {
            "machinename": "Machine Group",
        }


class WorkTypeForm(BaseStyledModelForm):
    class Meta:
        model = TblWorkType
        fields = ["worktype"]
        labels = {
            "worktype": "Type of Work",
        }


class StatusForm(BaseStyledModelForm):
    class Meta:
        model = TblStatus
        fields = ["status"]
        labels = {
            "status": "Type of Request Status",
        }


class ApprovalForm(BaseStyledModelForm):
    class Meta:
        model = TblApproval
        fields = ["approvalname", "approvaldept"]
        labels = {
            "approvalname": "Approving Person",
            "approvaldept": "Department",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dept_choices = [("", "Select Department")] + [
            (name, name) for name in TblDepartment.objects.order_by("depname").values_list("depname", flat=True)
        ]
        selected_department = ""
        if self.is_bound:
            selected_department = str(self.data.get("approvaldept", "")).strip()
        if not selected_department:
            selected_department = str(self.initial.get("approvaldept", "")).strip()
        current_department = str(getattr(self.instance, "approvaldept", "") or "").strip()
        if current_department and all(current_department != value for value, _ in dept_choices):
            dept_choices.append((current_department, current_department))
        self.fields["approvaldept"] = forms.ChoiceField(
            choices=dept_choices,
            required=True,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        self.fields["approvaldept"].label = "Department"

        approval_choices = [("", "Select Approving Person")] + _active_admin_choices(selected_department)
        current_name = str(getattr(self.instance, "approvalname", "") or "").strip()
        if current_name and all(current_name != value for value, _ in approval_choices):
            approval_choices.append((current_name, current_name))
        self.fields["approvalname"] = forms.ChoiceField(
            choices=approval_choices,
            required=True,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        self.fields["approvalname"].label = "Approving Person"

    def clean(self):
        cleaned = super().clean()
        selected_department = str(cleaned.get("approvaldept", "") or "").strip()
        selected_approval = str(cleaned.get("approvalname", "") or "").strip()
        if selected_department and selected_approval:
            allowed = {name.lower() for name, _ in _active_admin_choices(selected_department)}
            if selected_approval.lower() not in allowed:
                self.add_error(
                    "approvalname",
                    "Selected approving person must be an active admin in the selected department.",
                )
        return cleaned


class PersonnelForm(BaseStyledModelForm):
    class Meta:
        model = TblPersonnel
        fields = ["personnelname", "personneldept", "personneldesig"]
        labels = {
            "personnelname": "Full Name",
            "personneldept": "Department",
            "personneldesig": "Designation",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dept_choices = [("", "Select Department")] + [
            (name, name) for name in TblDepartment.objects.order_by("depname").values_list("depname", flat=True)
        ]
        current_department = str(getattr(self.instance, "personneldept", "") or "").strip()
        if current_department and all(current_department != value for value, _ in dept_choices):
            dept_choices.append((current_department, current_department))
        self.fields["personneldept"] = forms.ChoiceField(
            choices=dept_choices,
            required=True,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        self.fields["personneldept"].label = "Department"


class RequestForm(BaseStyledModelForm):
    class Meta:
        model = TblRequest
        fields = [
            "requestor",
            "department",
            "requestdept",
            "machinegroup",
            "worktype",
            "approval",
            "description",
            "dateneeded",
            "personnel",
            "status",
            "notes",
        ]
        widgets = {
            "dateneeded": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class UserRequestForm(BaseStyledModelForm):
    consent = forms.BooleanField(
        required=True,
        label=(
            "I have read about the Data Privacy Statement and consent to processing my personal data for this request."
        ),
    )
    reference_file = forms.FileField(required=False, label="Upload File for Reference")

    class Meta:
        model = TblRequest
        fields = [
            "requestor",
            "department",
            "requestdept",
            "machinegroup",
            "worktype",
            "approval",
            "description",
            "dateneeded",
            "personnel",
            "status",
            "notes",
            "dateupdated",
            "verifiedby",
            "findings",
            "verifiednote",
            "verifieddate",
        ]
        widgets = {
            "dateneeded": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 5}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "verifiednote": forms.Textarea(attrs={"rows": 3}),
            "dateupdated": forms.DateInput(attrs={"type": "date"}),
            "verifieddate": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dept_choices = [("", "Select Department")] + [
            (name, name) for name in TblDepartment.objects.order_by("depname").values_list("depname", flat=True)
        ]
        machine_choices = [("", "Select Machine Group")] + [
            (name, name) for name in TblMachineGroup.objects.order_by("machinename").values_list("machinename", flat=True)
        ]
        work_type_choices = [("", "Select Work Type")] + [
            (name, name) for name in TblWorkType.objects.order_by("worktype").values_list("worktype", flat=True)
        ]
        selected_approval_department = ""
        if self.is_bound:
            selected_approval_department = str(self.data.get("requestdept", "")).strip()
        if not selected_approval_department:
            selected_approval_department = str(self.initial.get("requestdept", "")).strip()
        if not selected_approval_department and self.current_user:
            selected_approval_department = str(self.current_user.userdepartment or "").strip()

        approval_choices = [("", "Select Approving Person")]
        seen_approvers = set()
        approvers_qs = TblApproval.objects.order_by("approvalname").only("approvalname", "approvaldept")
        for item in approvers_qs:
            item_dept = str(item.approvaldept or "").strip()
            if selected_approval_department and item_dept.lower() != selected_approval_department.lower():
                continue
            admin_name = str(item.approvalname or "").strip()
            if not admin_name:
                continue
            key = admin_name.lower()
            if key in seen_approvers:
                continue
            seen_approvers.add(key)
            approval_choices.append((admin_name, admin_name))
        personnel_choices = [("", "Select Personnel")] + [
            (name, name) for name in TblPersonnel.objects.order_by("personnelname").values_list("personnelname", flat=True)
        ]
        status_choices = [("", "Select Status")] + [
            (name, name) for name in TblStatus.objects.order_by("status").values_list("status", flat=True)
        ]
        if ("NEW", "NEW") not in status_choices:
            status_choices.append(("NEW", "NEW"))
        if (STATUS_PENDING_APPROVAL, STATUS_PENDING_APPROVAL) not in status_choices:
            status_choices.append((STATUS_PENDING_APPROVAL, STATUS_PENDING_APPROVAL))

        self.fields["department"] = forms.ChoiceField(choices=dept_choices, required=True, widget=forms.Select())
        self.fields["requestdept"] = forms.ChoiceField(choices=dept_choices, required=True, widget=forms.Select())
        self.fields["machinegroup"] = forms.ChoiceField(choices=machine_choices, required=True, widget=forms.Select())
        self.fields["worktype"] = forms.ChoiceField(choices=work_type_choices, required=True, widget=forms.Select())
        self.fields["approval"] = forms.ChoiceField(choices=approval_choices, required=True, widget=forms.Select())
        self.fields["personnel"] = forms.ChoiceField(choices=personnel_choices, required=False, widget=forms.Select())
        self.fields["status"] = forms.ChoiceField(choices=status_choices, required=False, widget=forms.Select())
        self.fields["dateupdated"].required = False
        self.fields["verifieddate"].required = False
        self.fields["verifiedby"].required = False
        self.fields["findings"].required = False
        self.fields["verifiednote"].required = False
        self.fields["notes"].required = False
        self.fields["verifieddate"].label = "Date Updated"

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

        if self.current_user:
            self.initial.setdefault("requestor", self.current_user.name)
            self.initial.setdefault("department", self.current_user.userdepartment)
            self.initial.setdefault("status", STATUS_PENDING_APPROVAL)
            self.fields["requestor"].widget.attrs["readonly"] = True
            self.fields["department"].disabled = True
            # Requester can only view request status/verifier sections.
            self.fields["personnel"].disabled = True
            self.fields["status"].disabled = True
            self.fields["findings"].disabled = True
            self.fields["notes"].widget.attrs["readonly"] = True
            self.fields["dateupdated"].widget.attrs["readonly"] = True
            self.fields["verifiedby"].widget.attrs["readonly"] = True
            self.fields["verifiednote"].widget.attrs["readonly"] = True
            self.fields["verifieddate"].widget.attrs["readonly"] = True

        self.fields["consent"].widget.attrs.pop("class", None)

    def clean(self):
        cleaned = super().clean()
        selected_request_dept = str(cleaned.get("requestdept", "")).strip()
        selected_approval = str(cleaned.get("approval", "")).strip()
        if selected_request_dept and selected_approval:
            allowed = set()
            approvers_qs = TblApproval.objects.order_by("approvalname").only("approvalname", "approvaldept")
            for item in approvers_qs:
                item_dept = str(item.approvaldept or "").strip()
                if item_dept.lower() != selected_request_dept.lower():
                    continue
                admin_name = str(item.approvalname or "").strip()
                if admin_name:
                    allowed.add(admin_name.lower())
            if selected_approval.lower() not in allowed:
                self.add_error("approval", "Selected approving person must be listed in Approval for the selected requested department.")
        return cleaned

    def clean_reference_file(self):
        uploaded = self.cleaned_data.get("reference_file")
        if not uploaded:
            return uploaded
        max_size = 5 * 1024 * 1024
        if uploaded.size and uploaded.size > max_size:
            raise forms.ValidationError("Reference file must be 5MB or smaller.")
        return uploaded


class UserProfileForm(BaseStyledModelForm):
    image_file = forms.FileField(required=False, label="Profile Image")

    class Meta:
        model = TblUsers
        fields = [
            "name",
            "username",
            "userdepartment",
            "useraddress",
            "usercontact",
        ]

    def clean_username(self):
        username = str(self.cleaned_data.get("username", "")).strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        exists = TblUsers.objects.filter(username__iexact=username).exclude(userid=self.instance.userid).exists()
        if exists:
            raise forms.ValidationError("This username is already taken.")
        return username

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded = self.cleaned_data.get("image_file")
        if uploaded:
            instance.userimage = uploaded.read()
        elif not instance.userimage:
            instance.userimage = b""
        if commit:
            instance.save()
        return instance


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        value = str(self.cleaned_data.get("current_password", ""))
        if not self.user or not verify_user_password(self.user, value):
            raise forms.ValidationError("Current password is incorrect.")
        return value

    def clean(self):
        cleaned = super().clean()
        new_password = str(cleaned.get("new_password", ""))
        confirm_password = str(cleaned.get("confirm_password", ""))
        if new_password and len(new_password) < 6:
            self.add_error("new_password", "New password must be at least 6 characters.")
        if new_password and len(new_password) > 50:
            self.add_error("new_password", "New password must be at most 50 characters.")
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "New passwords do not match.")
        return cleaned
