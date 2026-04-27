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


class BaseStyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class UserForm(BaseStyledModelForm):
    image_file = forms.FileField(required=False)

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
            "userstatus": forms.Select(
                choices=(
                    ("ACTIVE", "ACTIVE"),
                    ("INACTIVE", "INACTIVE"),
                )
            ),
        }

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


class DepartmentForm(BaseStyledModelForm):
    class Meta:
        model = TblDepartment
        fields = ["depname"]


class MachineForm(BaseStyledModelForm):
    class Meta:
        model = TblMachineGroup
        fields = ["machinename"]


class WorkTypeForm(BaseStyledModelForm):
    class Meta:
        model = TblWorkType
        fields = ["worktype"]


class StatusForm(BaseStyledModelForm):
    class Meta:
        model = TblStatus
        fields = ["status"]


class ApprovalForm(BaseStyledModelForm):
    class Meta:
        model = TblApproval
        fields = ["approvalname"]


class PersonnelForm(BaseStyledModelForm):
    class Meta:
        model = TblPersonnel
        fields = ["personnelname", "personneldept", "personneldesig"]


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
        approval_choices = [("", "Select Approving Person")] + [
            (name, name) for name in TblApproval.objects.order_by("approvalname").values_list("approvalname", flat=True)
        ]
        personnel_choices = [("", "Select Personnel")] + [
            (name, name) for name in TblPersonnel.objects.order_by("personnelname").values_list("personnelname", flat=True)
        ]
        status_choices = [("", "Select Status")] + [
            (name, name) for name in TblStatus.objects.order_by("status").values_list("status", flat=True)
        ]
        if ("NEW", "NEW") not in status_choices:
            status_choices.append(("NEW", "NEW"))

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
            self.initial.setdefault("status", "NEW")
            self.fields["requestor"].widget.attrs["readonly"] = True

        self.fields["consent"].widget.attrs.pop("class", None)


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
        if not self.user or value != str(self.user.userpassword):
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
