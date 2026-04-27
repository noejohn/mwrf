from datetime import date

from django.db import models


class TblUsers(models.Model):
    userid = models.AutoField(db_column="USERID", primary_key=True)
    name = models.CharField(db_column="NAME", max_length=50)
    userdepartment = models.CharField(db_column="USERDEPARTMENT", max_length=50)
    useraddress = models.CharField(db_column="USERADDRESS", max_length=25)
    usercontact = models.CharField(db_column="USERCONTACT", max_length=15)
    userposition = models.CharField(db_column="USERPOSITION", max_length=25)
    username = models.CharField(db_column="USERNAME", max_length=50)
    userpassword = models.CharField(db_column="USERPASSWORD", max_length=50)
    userstatus = models.CharField(db_column="USERSTATUS", max_length=10, default="ACTIVE")
    userimage = models.BinaryField(db_column="USERIMAGE", default=bytes)

    class Meta:
        managed = False
        db_table = "tblusers"

    def __str__(self) -> str:
        return f"{self.userid} - {self.name}"


class TblDepartment(models.Model):
    deptno = models.AutoField(db_column="DEPTNO", primary_key=True)
    depname = models.CharField(db_column="DEPNAME", max_length=50)

    class Meta:
        managed = False
        db_table = "tbldepartment"

    def __str__(self) -> str:
        return self.depname


class TblMachineGroup(models.Model):
    machineno = models.AutoField(db_column="machineno", primary_key=True)
    machinename = models.CharField(db_column="machinename", max_length=50)

    class Meta:
        managed = False
        db_table = "tblmachinegroup"

    def __str__(self) -> str:
        return self.machinename


class TblWorkType(models.Model):
    workno = models.AutoField(db_column="workno", primary_key=True)
    worktype = models.CharField(db_column="worktype", max_length=50)

    class Meta:
        managed = False
        db_table = "tblworktype"

    def __str__(self) -> str:
        return self.worktype


class TblStatus(models.Model):
    statusno = models.AutoField(db_column="statusno", primary_key=True)
    status = models.CharField(db_column="status", max_length=50)

    class Meta:
        managed = False
        db_table = "tblstatus"

    def __str__(self) -> str:
        return self.status


class TblApproval(models.Model):
    approvalno = models.IntegerField(db_column="APPROVALNO", primary_key=True)
    approvalname = models.CharField(db_column="APPROVALNAME", max_length=50)

    class Meta:
        managed = False
        db_table = "tblapproval"

    def __str__(self) -> str:
        return self.approvalname


class TblPersonnel(models.Model):
    personnelno = models.AutoField(db_column="personnelno", primary_key=True)
    personnelname = models.CharField(db_column="personnelname", max_length=50)
    personneldept = models.CharField(db_column="personneldept", max_length=25)
    personneldesig = models.CharField(db_column="personneldesig", max_length=25)

    class Meta:
        managed = False
        db_table = "tblpersonnel"

    def __str__(self) -> str:
        return self.personnelname


class TblRequest(models.Model):
    requestno = models.AutoField(db_column="requestno", primary_key=True)
    requestdate = models.DateField(db_column="requestdate")
    requestor = models.CharField(db_column="requestor", max_length=50)
    department = models.CharField(db_column="department", max_length=50)
    requestdept = models.CharField(db_column="requestdept", max_length=50)
    machinegroup = models.CharField(db_column="machinegroup", max_length=50)
    worktype = models.CharField(db_column="worktype", max_length=50)
    approval = models.CharField(db_column="approval", max_length=50)
    description = models.CharField(db_column="description", max_length=200)
    dateneeded = models.DateField(db_column="dateneeded")
    personnel = models.CharField(db_column="personnel", max_length=50)
    status = models.CharField(db_column="status", max_length=50, default="NEW")
    notes = models.CharField(db_column="notes", max_length=200, default="", blank=True)
    dateupdated = models.DateField(db_column="dateupdated", default=date.today)
    verifiedby = models.CharField(db_column="verifiedby", max_length=50, default="", blank=True)
    findings = models.CharField(db_column="findings", max_length=50, default="", blank=True)
    verifiednote = models.CharField(db_column="verifiednote", max_length=100, default="", blank=True)
    verifieddate = models.DateField(db_column="verifieddate", default=date.today)

    class Meta:
        managed = False
        db_table = "tblrequest"

    def __str__(self) -> str:
        return f"REQ-{self.requestno}"

# Create your models here.
