import React from "react";
import * as ReactDOMClient from "react-dom/client";

window.React = React;
window.ReactDOM = ReactDOMClient;

(function () {
    const shellData = JSON.parse(document.getElementById("shell-ui-data").textContent || "{}");
    const pageData = JSON.parse(document.getElementById("page-ui-data").textContent || "{}");
    const pageType = window.CORE_PAGE_TYPE || "";
    const csrfToken = window.CORE_CSRF_TOKEN || "";

    function htmlContent(markup) {
        return { __html: markup || "" };
    }

    function buildUrl(template, pk) {
        return (template || "").replace("/0/", `/${pk}/`);
    }

    function FieldErrors({ errors }) {
        if (!errors || errors.length === 0) return null;
        return errors.map((error, idx) => (
            <small key={`error-${idx}`} className="field-error">{error}</small>
        ));
    }

    function GenericField({ field }) {
        if (!field) return null;
        return (
            <label className="field-label">
                <span>{field.label}</span>
                <span dangerouslySetInnerHTML={htmlContent(field.widgetHtml)} />
                <FieldErrors errors={field.errors} />
            </label>
        );
    }

    function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onCancel, confirmClassName }) {
        React.useEffect(() => {
            if (!open) return undefined;
            function onEscape(event) {
                if (event.key === "Escape") {
                    onCancel();
                }
            }
            document.addEventListener("keydown", onEscape);
            return () => document.removeEventListener("keydown", onEscape);
        }, [open, onCancel]);

        if (!open) return null;

        return (
            <div className="logout-modal">
                <div className="logout-backdrop" onClick={onCancel}></div>
                <div className="logout-dialog" role="dialog" aria-modal="true">
                    <h3>{title}</h3>
                    <p>{message}</p>
                    <div className="logout-actions">
                        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
                        <button
                            type="button"
                            className={confirmClassName || "btn btn-danger"}
                            onClick={onConfirm}
                        >
                            {confirmLabel || "Confirm"}
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    function MetricCard({ label, value, tone }) {
        const className = tone ? `metric-count ${tone}` : "metric-count";
        return (
            <div className="metric-card">
                <div className={className}>{value}</div>
                <div className="metric-label">{label}</div>
            </div>
        );
    }

    function DashboardPage({ data }) {
        const metricCards = [
            { label: "ALL REQUEST", value: data.counts.all, tone: "" },
            { label: "NEW", value: data.counts.new, tone: "blue" },
            { label: "ON-GOING", value: data.counts.on_going, tone: "yellow" },
            { label: "FOR VERIFICATION", value: data.counts.verification, tone: "green-dark" },
            { label: "CLOSED", value: data.counts.done, tone: "green" },
            { label: "REJECTED", value: data.counts.rejected, tone: "red" },
        ];

        return (
            <section className="page-card">
                <header className="page-header">
                    <h1>DASHBOARD</h1>
                </header>

                <div className="section-title">Request overview</div>
                <div className="metric-grid">
                    {metricCards.map((item) => (
                        <MetricCard key={item.label} label={item.label} value={item.value} tone={item.tone} />
                    ))}
                </div>

                <div className="overview-grid">
                    <section className="panel-card">
                        <h3>REQUEST BY STATUS</h3>
                        <div className="status-list">
                            {data.statusRows.map((row) => (
                                <div className="status-row" key={row.label}>
                                    <span>{row.label}</span>
                                    <span className="status-bar"></span>
                                    <strong>{row.count}</strong>
                                </div>
                            ))}
                        </div>
                    </section>

                    <section className="panel-card">
                        <h3>QUICK LINKS</h3>
                        <div className="quick-links">
                            <a href={data.quickLinks.newRequest}>New work request</a>
                            <a href={data.quickLinks.verification}>Pending verifications</a>
                            <a href={data.quickLinks.onGoing}>On-going requests</a>
                            <a href={data.quickLinks.rejected}>Rejected requests</a>
                        </div>
                    </section>
                </div>

                <section className="panel-card table-section">
                    <h3>Recent requests</h3>
                    <div className="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>NO.</th>
                                    <th>REQUESTED BY</th>
                                    <th>MACHINE</th>
                                    <th>WORK TYPE</th>
                                    <th>DATE FILLED</th>
                                    <th>STATUS</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.recentRequests.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" className="empty">No requests yet.</td>
                                    </tr>
                                ) : (
                                    data.recentRequests.map((req) => (
                                        <tr key={req.requestno}>
                                            <td>{req.requestno}</td>
                                            <td>{req.requestor}</td>
                                            <td>{req.machinegroup}</td>
                                            <td>{req.worktype}</td>
                                            <td>{req.requestdate}</td>
                                            <td>{req.status}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>
            </section>
        );
    }

    function EntityForm({ data }) {
        function renderField(field, index) {
            return (
                <label className="field-label" key={`${field.name}-${index}`}>
                    <span>{field.label}</span>
                    <span dangerouslySetInnerHTML={htmlContent(field.widgetHtml)} />
                    <FieldErrors errors={field.errors} />
                </label>
            );
        }

        const isUsersEntity = data.entity === "users";
        const isPersonnelEntity = data.entity === "personnel";
        const isDepartmentEntity = data.entity === "departments";
        const isMachineEntity = data.entity === "machines";
        const isWorkTypeEntity = data.entity === "work-types";
        const isApprovalEntity = data.entity === "approvals";
        const isStatusEntity = data.entity === "statuses";
        const formFieldsByName = React.useMemo(() => {
            const map = {};
            (data.formFields || []).forEach((field) => {
                if (!field || !field.name) return;
                map[field.name] = field;
            });
            return map;
        }, [data.formFields]);
        const approvalDeptField = formFieldsByName.approvaldept || null;
        const approvalNameField = formFieldsByName.approvalname || null;
        const approvalDeptOptions = data.approvalDeptOptions || [];
        const approvalAdminsByDepartment = data.approvalAdminsByDepartment || {};
        const [selectedApprovalDept, setSelectedApprovalDept] = React.useState(data.selectedApprovalDept || "");
        const [selectedApprovalName, setSelectedApprovalName] = React.useState(data.selectedApprovalName || "");

        React.useEffect(() => {
            setSelectedApprovalDept(data.selectedApprovalDept || "");
            setSelectedApprovalName(data.selectedApprovalName || "");
        }, [data.selectedApprovalDept, data.selectedApprovalName]);

        function normalizeDepartment(value) {
            return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
        }

        function getApprovalOptionsByDepartment(department) {
            const direct = approvalAdminsByDepartment[department];
            if (Array.isArray(direct)) {
                return direct;
            }
            const target = normalizeDepartment(department);
            const matchedKey = Object.keys(approvalAdminsByDepartment).find(
                (key) => normalizeDepartment(key) === target
            );
            return matchedKey ? (approvalAdminsByDepartment[matchedKey] || []) : [];
        }

        const filteredApprovalOptions = isApprovalEntity
            ? getApprovalOptionsByDepartment(selectedApprovalDept)
            : [];
        const approvalOptions = [...filteredApprovalOptions];
        if (isApprovalEntity && selectedApprovalName && !approvalOptions.includes(selectedApprovalName)) {
            approvalOptions.unshift(selectedApprovalName);
        }

        function onApprovalDepartmentChange(event) {
            const nextDepartment = event.target.value;
            const nextOptions = getApprovalOptionsByDepartment(nextDepartment);
            const keepCurrent = nextOptions.includes(selectedApprovalName);
            setSelectedApprovalDept(nextDepartment);
            setSelectedApprovalName(keepCurrent ? selectedApprovalName : "");
        }

        const formTitle = isUsersEntity
            ? (data.editing ? "Update User Account" : "Create User Account")
            : isPersonnelEntity
                ? (data.editing ? "UPDATE PERSONNEL INFORMATION" : "ADD PERSONNEL INFORMATION")
                : isDepartmentEntity
                    ? (data.editing ? "UPDATE ORGANIZATION DEPARTMENT" : "ADD ORGANIZATION DEPARTMENT")
                    : isMachineEntity
                        ? (data.editing ? "UPDATE TYPE OF MACHINE" : "ADD TYPE OF MACHINE")
                        : isWorkTypeEntity
                            ? (data.editing ? "UPDATE WORK TYPE" : "ADD WORK TYPE")
                            : isApprovalEntity
                                ? (data.editing ? "UPDATE APPROVING PERSON" : "ADD APPROVING PERSON")
                                : isStatusEntity
                                    ? (data.editing ? "UPDATE STATUS OF WORK REQUEST" : "ADD STATUS OF WORK REQUEST")
                : (data.editing ? "Update Record" : "Create Record");

        return (
            <section className="panel-card">
                <h3>{formTitle}</h3>
                <form method="post" encType="multipart/form-data" className="crud-form">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    {isApprovalEntity ? (
                        <>
                            <label className="field-label">
                                <span>{(approvalDeptField || {}).label || "Department"}</span>
                                <select
                                    name="approvaldept"
                                    className="form-control"
                                    value={selectedApprovalDept}
                                    onChange={onApprovalDepartmentChange}
                                >
                                    {approvalDeptOptions.map((item) => (
                                        <option key={`${item.value}-${item.label}`} value={item.value}>{item.label}</option>
                                    ))}
                                </select>
                                <FieldErrors errors={(approvalDeptField || {}).errors || []} />
                            </label>

                            <label className="field-label">
                                <span>{(approvalNameField || {}).label || "Approving Person"}</span>
                                <select
                                    name="approvalname"
                                    className="form-control"
                                    value={selectedApprovalName}
                                    onChange={(event) => setSelectedApprovalName(event.target.value)}
                                >
                                    <option value="">Select Approving Person</option>
                                    {approvalOptions.map((name) => (
                                        <option key={name} value={name}>{name}</option>
                                    ))}
                                </select>
                                <FieldErrors errors={(approvalNameField || {}).errors || []} />
                            </label>
                        </>
                    ) : null}
                    {data.formFields.map((field, index) => (
                        <React.Fragment key={`${field.name}-${index}`}>
                            {isApprovalEntity && (field.name === "approvalname" || field.name === "approvaldept")
                                ? null
                                : (
                                    <>
                                        {isUsersEntity && field.name === "username" ? (
                                            <h4 className="form-section-title">Create Login Account</h4>
                                        ) : null}
                                        {renderField(field, index)}
                                    </>
                                )}
                        </React.Fragment>
                    ))}
                    <div className="form-actions">
                        <button type="submit" className="btn btn-primary">
                            {data.editing ? "Update" : "Save"}
                        </button>
                        {data.editing ? <a href={data.urls.cancel} className="btn">Cancel</a> : null}
                    </div>
                </form>
            </section>
        );
    }

    function EntityTable({ data }) {
        const [deleteForm, setDeleteForm] = React.useState(null);

        function onDeleteSubmit(event) {
            event.preventDefault();
            setDeleteForm(event.currentTarget);
        }

        function closeDeleteModal() {
            setDeleteForm(null);
        }

        function confirmDelete() {
            if (deleteForm) {
                deleteForm.submit();
            }
            closeDeleteModal();
        }

        return (
            <>
                <section className="panel-card">
                    <h3>{data.title} List</h3>
                    <div className="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    {data.tableHeaders.map((header) => (
                                        <th key={header.key}>{header.label.toUpperCase()}</th>
                                    ))}
                                    <th>ACTIONS</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.records.length === 0 ? (
                                    <tr>
                                        <td colSpan={data.emptyColspan} className="empty">No records found.</td>
                                    </tr>
                                ) : (
                                    data.records.map((row) => (
                                        <tr key={row.pk}>
                                            {data.tableHeaders.map((header) => (
                                                <td key={`${row.pk}-${header.key}`}>{row.values[header.key] || ""}</td>
                                            ))}
                                            <td>
                                                <div className="row-actions">
                                                    <a
                                                        href={buildUrl(data.urls.editTemplate, row.pk)}
                                                        className="btn btn-mini"
                                                    >
                                                        Edit
                                                    </a>

                                                    {data.entity === "users" ? (
                                                        <form
                                                            method="post"
                                                            action={buildUrl(data.urls.toggleUserTemplate, row.pk)}
                                                            className="inline"
                                                        >
                                                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                                            <button type="submit" className="btn btn-mini">
                                                                {row.userstatus === "ACTIVE" ? "Set Inactive" : "Set Active"}
                                                            </button>
                                                        </form>
                                                    ) : null}

                                                    <form
                                                        method="post"
                                                        action={buildUrl(data.urls.deleteTemplate, row.pk)}
                                                        className="inline"
                                                        onSubmit={onDeleteSubmit}
                                                    >
                                                        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                                        <button type="submit" className="btn btn-mini btn-danger">Delete</button>
                                                    </form>
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>
                <ConfirmDialog
                    open={Boolean(deleteForm)}
                    title="Delete Record"
                    message="Are you sure you want to delete this record?"
                    confirmLabel="Delete"
                    confirmClassName="btn btn-danger"
                    onCancel={closeDeleteModal}
                    onConfirm={confirmDelete}
                />
            </>
        );
    }

    function EntityPage({ data }) {
        return (
            <section className="page-card">
                <header className="page-header">
                    <h1>{data.title.toUpperCase()}</h1>
                </header>

                <div className="crud-grid">
                    <EntityForm data={data} />
                    <EntityTable data={data} />
                </div>
            </section>
        );
    }

    function UserRequestField({ field, label }) {
        if (!field) return null;
        return (
            <>
                <label className="user-field">
                    <span>{label || field.label}</span>
                    <span dangerouslySetInnerHTML={htmlContent(field.widgetHtml)} />
                </label>
                <FieldErrors errors={field.errors} />
            </>
        );
    }

    function UserRequestMode({ data }) {
        const fields = data.formFieldsByName || {};
        const requestRows = data.records || [];
        const userPageMode = String(data.userPageMode || "make");
        const showMakePage = userPageMode === "make";
        const showMyPage = userPageMode === "my";
        const requestDeptOptions = data.requestDeptOptions || [];
        const departmentApprovers = data.departmentApprovers || {};
        const initialRequestedDept = data.selectedRequestedDept || "";
        const initialApproval = data.selectedApproval || "";
        const [requestedDept, setRequestedDept] = React.useState(initialRequestedDept);
        const [approval, setApproval] = React.useState(initialApproval);
        const [selectedRequestNo, setSelectedRequestNo] = React.useState(
            requestRows.length ? requestRows[0].requestno : null
        );

        React.useEffect(() => {
            if (!requestRows.length) {
                setSelectedRequestNo(null);
                return;
            }
            const exists = requestRows.some((item) => item.requestno === selectedRequestNo);
            if (!exists) {
                setSelectedRequestNo(requestRows[0].requestno);
            }
        }, [requestRows, selectedRequestNo]);

        const selectedRequest = requestRows.find((row) => row.requestno === selectedRequestNo) || null;

        function normalizeDepartment(value) {
            return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
        }

        function isVerificationStatus(value) {
            const normalized = String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
            return (
                normalized.includes("verification") ||
                normalized.includes("forverification") ||
                normalized.includes("verify") ||
                normalized.includes("submit")
            );
        }

        let approverOptions = departmentApprovers[requestedDept] || [];
        if (!approverOptions.length && requestedDept) {
            const target = normalizeDepartment(requestedDept);
            const matchedKey = Object.keys(departmentApprovers).find(
                (key) => normalizeDepartment(key) === target
            );
            if (matchedKey) {
                approverOptions = departmentApprovers[matchedKey] || [];
            }
        }
        const approvalValue = approverOptions.includes(approval) ? approval : "";

        function onRequestDeptChange(event) {
            setRequestedDept(event.target.value);
            setApproval("");
        }

        function onFormReset() {
            setRequestedDept(initialRequestedDept);
            setApproval(initialApproval);
        }

        return (
            <>
                {showMakePage ? (
                    <section className="user-request-entry">
                        <form method="post" encType="multipart/form-data" className="user-request-form" onReset={onFormReset}>
                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />

                            <div className="user-request-head">
                                <span>ID: WR-{data.nextRequestNo || "--"}</span>
                                <strong>CREATE WORK REQUEST</strong>
                            </div>

                            <div className="user-request-top-grid">
                                <div className="user-form-col">
                                    <label className="user-field">
                                        <span>Date Requested</span>
                                        <input type="text" className="preview-input" value={data.todayDate || "-"} readOnly />
                                    </label>
                                    <UserRequestField field={fields.requestor} label="Requestor" />
                                    <UserRequestField field={fields.department} label="Department" />
                                    <label className="user-field">
                                        <span>Requested Dept</span>
                                        <select className="form-control" name="requestdept" value={requestedDept} onChange={onRequestDeptChange}>
                                            {requestDeptOptions.map((item) => (
                                                <option key={`${item.value}-${item.label}`} value={item.value}>{item.label}</option>
                                            ))}
                                        </select>
                                    </label>
                                    <FieldErrors errors={(fields.requestdept || {}).errors || []} />
                                </div>

                                <div className="user-form-col">
                                    <UserRequestField field={fields.machinegroup} label="Machine Group" />
                                    <UserRequestField field={fields.worktype} label="Type of Work" />
                                    <label className="user-field">
                                        <span>Approving Person</span>
                                        <select
                                            className="form-control"
                                            name="approval"
                                            value={approvalValue}
                                            onChange={(event) => setApproval(event.target.value)}
                                            disabled={!requestedDept}
                                        >
                                            {!requestedDept ? (
                                                <option value="">Select Requested Dept first</option>
                                            ) : (
                                                <option value="">Select Approving Person</option>
                                            )}
                                            {approverOptions.map((name) => (
                                                <option key={name} value={name}>{name}</option>
                                            ))}
                                        </select>
                                    </label>
                                    <FieldErrors errors={(fields.approval || {}).errors || []} />
                                    <UserRequestField field={fields.dateneeded} label="Date Needed" />
                                </div>

                                <div className="user-form-col">
                                    <UserRequestField field={fields.description} label="Description" />
                                    <UserRequestField field={fields.reference_file} label="Upload File for Reference" />
                                </div>
                            </div>

                            <div className="user-request-bottom-grid">
                                <section className="user-consent-card">
                                    <label className="consent-line">
                                        <span dangerouslySetInnerHTML={htmlContent((fields.consent || {}).widgetHtml)} />
                                        <span>{(fields.consent || {}).label || ""}</span>
                                    </label>
                                    <FieldErrors errors={(fields.consent || {}).errors || []} />
                                    <div className="user-request-actions">
                                        <button type="submit" className="btn btn-primary">Proceed</button>
                                        <button type="reset" className="btn">Clear</button>
                                    </div>
                                </section>
                            </div>
                        </form>
                    </section>
                ) : null}

                {showMyPage ? (
                    <>
                        <div className="user-request-bottom-grid my-request-grid">
                            <section className="user-readonly-card">
                                <h4>REQUEST STATUS</h4>
                                <small>{selectedRequest ? `Request WR-${selectedRequest.requestno}` : "Select a request below"}</small>
                                <p><b>Personnel:</b> <span>{selectedRequest ? selectedRequest.personnel : "-"}</span></p>
                                <p><b>Status:</b> <span>{selectedRequest ? selectedRequest.status : "-"}</span></p>
                                <p><b>Notes:</b> <span>{selectedRequest ? selectedRequest.notes : "-"}</span></p>
                                <p><b>Date Updated:</b> <span>{selectedRequest ? selectedRequest.dateupdated : "-"}</span></p>
                                {selectedRequest && isVerificationStatus(selectedRequest.status) ? (
                                    <div className="row-actions">
                                        <form method="post" action={buildUrl(data.urls.userVerifyTemplate, selectedRequest.requestno)} className="inline">
                                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                            <button type="submit" className="btn btn-primary btn-mini">Verified & Close</button>
                                        </form>
                                        <form method="post" action={buildUrl(data.urls.userBackjobTemplate, selectedRequest.requestno)} className="inline">
                                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                            <button type="submit" className="btn btn-danger btn-mini">Back Job</button>
                                        </form>
                                    </div>
                                ) : null}
                            </section>

                            <section className="user-readonly-card">
                                <h4>WORK REQUEST VERIFIER</h4>
                                <small>{selectedRequest ? `Request WR-${selectedRequest.requestno}` : "Select a request below"}</small>
                                <p><b>Verified by:</b> <span>{selectedRequest ? selectedRequest.verifiedby : "-"}</span></p>
                                <p><b>Findings:</b> <span>{selectedRequest ? selectedRequest.findings : "-"}</span></p>
                                <p><b>Verified Note:</b> <span>{selectedRequest ? selectedRequest.verifiednote : "-"}</span></p>
                                <p><b>Date Verified:</b> <span>{selectedRequest ? selectedRequest.verifieddate : "-"}</span></p>
                            </section>
                        </div>

                        <section className="user-ongoing-panel">
                            <div className="user-ongoing-head">
                                <h3>MY REQUESTS</h3>
                            </div>
                            <div className="table-wrap">
                                <table className="user-ongoing-table">
                                    <thead>
                                        <tr>
                                            <th>REQUEST NO.</th>
                                            <th>DATE REQUESTED</th>
                                            <th>MACHINE GROUP</th>
                                            <th>WORK TYPE</th>
                                            <th>STATUS</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {requestRows.length === 0 ? (
                                            <tr>
                                                <td colSpan="5" className="empty">No requests found.</td>
                                            </tr>
                                        ) : (
                                            requestRows.map((row) => (
                                                <tr
                                                    key={`my-request-${row.requestno}`}
                                                    className={selectedRequestNo === row.requestno ? "request-row active" : "request-row"}
                                                    onClick={() => setSelectedRequestNo(row.requestno)}
                                                >
                                                    <td><span className="request-link">WR-{row.requestno}</span></td>
                                                    <td>{row.requestdate}</td>
                                                    <td>{row.machinegroup}</td>
                                                    <td>{row.worktype}</td>
                                                    <td><span className="status-pill">{row.status}</span></td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    </>
                ) : null}
            </>
        );
    }

    function AdminRequestMode({ data }) {
        const [selectedRequestNo, setSelectedRequestNo] = React.useState(
            data.records.length ? data.records[0].requestno : null
        );
        const [deleteForm, setDeleteForm] = React.useState(null);
        const [warningMessage, setWarningMessage] = React.useState("");
        const personnelByDepartment = data.personnelByDepartment || {};
        const statusOptions = data.requestStatusOptions || [];
        const findingsOptions = data.findingsOptions || [];
        const currentApproverName = data.currentApproverName || "";
        const permissions = data.permissions || {};
        const isSuperadminView = Boolean(data.isSuperadmin);
        const canRequestAction = Boolean(permissions.canRequestAction);
        const canRequestOperations = Boolean(permissions.canRequestOperations);
        const canRequestApproval = Boolean(permissions.canRequestApproval);
        const canRequestVerificationFields = Boolean(permissions.canRequestVerificationFields);
        const workflowStatuses = data.workflowStatuses || {};
        const statusPendingApproval = workflowStatuses.pendingApproval || "PENDING APPROVAL";
        const statusApproved = workflowStatuses.approved || "APPROVED";
        const statusOnGoing = workflowStatuses.onGoing || "ON GOING";
        const statusForVerification = workflowStatuses.forVerification || "FOR VERIFICATION";
        const statusBackJob = workflowStatuses.backJob || "BACK JOB";
        const statusClosed = workflowStatuses.closed || "CLOSED";
        const statusRejected = workflowStatuses.rejected || "REJECTED";

        React.useEffect(() => {
            if (!data.records.length) {
                setSelectedRequestNo(null);
                return;
            }
            const exists = data.records.some((item) => item.requestno === selectedRequestNo);
            if (!exists) {
                setSelectedRequestNo(data.records[0].requestno);
            }
        }, [data.records, selectedRequestNo]);

        const selected = data.records.find((row) => row.requestno === selectedRequestNo) || null;
        const [selectedPersonnel, setSelectedPersonnel] = React.useState(selected ? (selected.personnel || "") : "");
        const [selectedStatus, setSelectedStatus] = React.useState(selected ? (selected.status || "") : "");
        const [selectedScheduleDate, setSelectedScheduleDate] = React.useState(selected ? (selected.dateneeded || "") : "");
        const [selectedNotes, setSelectedNotes] = React.useState(selected ? (selected.notes || "") : "");
        const [selectedFindings, setSelectedFindings] = React.useState(selected ? (selected.findings || "") : "");
        const [selectedVerifiedNote, setSelectedVerifiedNote] = React.useState(selected ? (selected.verifiednote || "") : "");

        React.useEffect(() => {
            if (!selected) {
                setSelectedPersonnel("");
                setSelectedStatus("");
                setSelectedScheduleDate("");
                setSelectedNotes("");
                setSelectedFindings("");
                setSelectedVerifiedNote("");
                return;
            }
            setSelectedPersonnel(selected.personnel || "");
            setSelectedStatus(selected.status || "");
            setSelectedScheduleDate(selected.dateneeded === "-" ? "" : (selected.dateneeded || ""));
            setSelectedNotes(selected.notes === "-" ? "" : (selected.notes || ""));
            setSelectedFindings(selected.findings === "-" ? "" : (selected.findings || ""));
            setSelectedVerifiedNote(selected.verifiednote === "-" ? "" : (selected.verifiednote || ""));
        }, [selectedRequestNo, selected]);

        function normalizeDepartment(value) {
            return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
        }

        function getPersonnelOptionsByDepartment(department) {
            const direct = personnelByDepartment[department];
            if (Array.isArray(direct)) {
                return direct;
            }
            const target = normalizeDepartment(department);
            const matchedKey = Object.keys(personnelByDepartment).find(
                (key) => normalizeDepartment(key) === target
            );
            return matchedKey ? (personnelByDepartment[matchedKey] || []) : [];
        }

        const personnelOptions = selected ? getPersonnelOptionsByDepartment(selected.requestdept) : [];
        const personnelValue = personnelOptions.includes(selectedPersonnel) ? selectedPersonnel : "";
        const statusValue = selectedStatus || "";
        const findingsValue = selectedFindings || "";

        function normalizeStatus(value) {
            return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
        }

        function statusEquals(left, right) {
            return normalizeStatus(left) === normalizeStatus(right);
        }

        function statusIsPending(value) {
            const normalized = normalizeStatus(value);
            return !normalized || normalized === "new" || normalized === "pendingapproval" || normalized === "pending";
        }

        function statusIsApproved(value) {
            return statusEquals(value, statusApproved);
        }

        function statusIsOnGoing(value) {
            const normalized = normalizeStatus(value);
            return normalized === "ongoing" || statusEquals(value, statusOnGoing);
        }

        function statusIsForVerification(value) {
            const normalized = normalizeStatus(value);
            return normalized === "forverification" || normalized === "verification" || normalized.includes("verify");
        }

        function statusIsBackJob(value) {
            return statusEquals(value, statusBackJob);
        }

        function statusIsClosedOrRejected(value) {
            return statusEquals(value, statusClosed) || statusEquals(value, statusRejected) || normalizeStatus(value) === "done";
        }

        function configuredStatusMatch(value) {
            const normalized = normalizeStatus(value);
            if (!normalized) return "";
            return statusOptions.find((item) => normalizeStatus(item) === normalized) || "";
        }

        function configuredStageOptions(values, currentStatus) {
            const seen = new Set();
            const resolved = [];
            values.forEach((value) => {
                const match = configuredStatusMatch(value);
                if (!match) return;
                const key = normalizeStatus(match);
                if (!key || seen.has(key)) return;
                seen.add(key);
                resolved.push(match);
            });
            const currentValue = String(currentStatus || "").trim();
            const currentKey = normalizeStatus(currentValue);
            if (currentValue && currentKey && !seen.has(currentKey)) {
                resolved.unshift(currentValue);
            }
            if (!resolved.length && statusOptions.length) {
                return [...statusOptions];
            }
            return resolved;
        }

        function getStageStatusOptions(currentStatus) {
            if (isSuperadminView && statusOptions.length) {
                return configuredStageOptions(statusOptions, currentStatus);
            }
            if (statusIsPending(currentStatus)) {
                return configuredStageOptions([statusApproved, statusRejected], currentStatus);
            }
            if (statusIsApproved(currentStatus)) {
                return configuredStageOptions([statusApproved, statusOnGoing], currentStatus);
            }
            if (statusIsBackJob(currentStatus)) {
                return configuredStageOptions([statusBackJob, statusOnGoing], currentStatus);
            }
            if (statusIsOnGoing(currentStatus)) {
                return configuredStageOptions([statusOnGoing, statusForVerification], currentStatus);
            }
            if (statusIsForVerification(currentStatus)) {
                return configuredStageOptions([statusForVerification, statusClosed], currentStatus);
            }
            if (statusIsClosedOrRejected(currentStatus)) {
                return configuredStageOptions([currentStatus], currentStatus);
            }
            return configuredStageOptions(
                [statusPendingApproval, statusApproved, statusOnGoing, statusForVerification, statusBackJob, statusClosed, statusRejected],
                currentStatus
            );
        }

        const allowedStatusOptions = selected ? getStageStatusOptions(selected.status || "") : statusOptions;
        const safeStatusValue = allowedStatusOptions.includes(statusValue) ? statusValue : (allowedStatusOptions[0] || "");
        const canEditSchedule = selected && (statusIsApproved(selected.status || "") || statusIsBackJob(selected.status || "") || statusIsOnGoing(selected.status || ""));
        const isReadOnlyStatus = selected && statusIsClosedOrRejected(selected.status || "");
        const awaitingAdminApproval = selected && statusIsPending(selected.status || "") && canRequestOperations && !canRequestApproval;
        const canEditOperationalFields = canRequestOperations && !awaitingAdminApproval;

        function requiresWorkDetails(currentStatus, targetStatus) {
            if (statusIsApproved(currentStatus) || statusIsBackJob(currentStatus) || statusIsOnGoing(currentStatus) || statusIsForVerification(currentStatus)) {
                return true;
            }
            if (
                statusIsOnGoing(targetStatus) ||
                statusIsForVerification(targetStatus) ||
                statusIsBackJob(targetStatus) ||
                statusIsClosedOrRejected(targetStatus)
            ) {
                return true;
            }
            return false;
        }

        function onSaveStatusSubmit(event) {
            if (!selected) {
                event.preventDefault();
                setWarningMessage("Select a request first.");
                return;
            }
            if (awaitingAdminApproval) {
                event.preventDefault();
                setWarningMessage("Admin or super admin must approve this request before personnel assignment.");
                return;
            }
            if (!canRequestOperations) {
                return;
            }
            if (isReadOnlyStatus) {
                event.preventDefault();
                setWarningMessage("Closed or rejected requests can no longer be updated.");
                return;
            }

            const targetStatus = safeStatusValue || "";
            const needsDetails = requiresWorkDetails(selected.status || "", targetStatus);
            if (!needsDetails) {
                return;
            }

            const assignedPersonnel = String(personnelValue || "").trim();
            const scheduleDate = String(selectedScheduleDate || "").trim();
            const workNotes = String(selectedNotes || "").trim();

            if (!assignedPersonnel || assignedPersonnel.toUpperCase() === "UNASSIGNED") {
                event.preventDefault();
                setWarningMessage("Please assign personnel first before saving status.");
                return;
            }

            if (!scheduleDate) {
                event.preventDefault();
                setWarningMessage("Please set the scheduled date first before saving status.");
                return;
            }

            if (!workNotes) {
                event.preventDefault();
                setWarningMessage("Please fill out the work details in Notes before saving status.");
            }
        }

        function onSaveVerificationSubmit(event) {
            if (!selected) {
                event.preventDefault();
                setWarningMessage("Select a request first.");
                return;
            }
            if (!canRequestVerificationFields) {
                event.preventDefault();
                setWarningMessage("You do not have permission to update verification details.");
                return;
            }
            if (isReadOnlyStatus) {
                event.preventDefault();
                setWarningMessage("Closed or rejected requests can no longer be updated.");
            }
        }

        function onDeleteSubmit(event) {
            event.preventDefault();
            setDeleteForm(event.currentTarget);
        }

        function closeDeleteModal() {
            setDeleteForm(null);
        }

        function closeWarningModal() {
            setWarningMessage("");
        }

        function confirmDelete() {
            if (deleteForm) {
                deleteForm.submit();
            }
            closeDeleteModal();
        }

        return (
            <>
                <header className="request-toolbar">
                    <h1>{data.filterLabel}</h1>
                    <form method="get" className="request-search">
                        <input type="text" name="q" placeholder="Search requests..." defaultValue={data.query || ""} />
                        <button type="submit">Search</button>
                    </form>
                </header>

                <section className="request-table-panel">
                    <div className={`table-wrap dark ${data.isSuperadmin ? "dark-superadmin" : ""}`}>
                        <table className={`request-table ${data.isSuperadmin ? "superadmin-wide" : ""}`}>
                            <thead>
                                <tr>
                                    {data.tableHeaders.map((header) => (
                                        <th key={header.key}>{header.label}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {data.records.length === 0 ? (
                                    <tr>
                                        <td colSpan={data.emptyColspan} className="empty">No requests found.</td>
                                    </tr>
                                ) : (
                                    data.records.map((row) => (
                                        <tr
                                            key={row.requestno}
                                            className={`request-row ${selectedRequestNo === row.requestno ? "active" : ""}`}
                                            onClick={() => setSelectedRequestNo(row.requestno)}
                                        >
                                            {data.tableHeaders.map((header) => {
                                                const value = row[header.key] || "-";
                                                if (header.key === "requestno") {
                                                    return (
                                                        <td key={`${row.requestno}-${header.key}`}>
                                                            <span className="request-link">WR-{value}</span>
                                                        </td>
                                                    );
                                                }
                                                if (header.key === "description" && data.isSuperadmin) {
                                                    return (
                                                        <td key={`${row.requestno}-${header.key}`} className="request-col-description-cell">
                                                            {value}
                                                        </td>
                                                    );
                                                }
                                                return <td key={`${row.requestno}-${header.key}`}>{value}</td>;
                                            })}
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>

                <section className="preview-section">
                    <div className="preview-header">
                        <strong>PREVIEW</strong>
                        <span>click a row to view details</span>
                        <small>{selected ? `selected request WR-${selected.requestno}` : "select a row above"}</small>
                    </div>
                    <div className="preview-grid">
                        <div className="preview-col details-col">
                            <p><b>Date Requested:</b> <span>{selected ? selected.requestdate : "-"}</span></p>
                            <p><b>Requestor:</b> <span>{selected ? selected.requestor : "-"}</span></p>
                            <p><b>Department:</b> <span>{selected ? selected.department : "-"}</span></p>
                            <p><b>Requested Dept:</b> <span>{selected ? selected.requestdept : "-"}</span></p>
                            <p><b>Machine Group:</b> <span>{selected ? selected.machinegroup : "-"}</span></p>
                            <p><b>Type of Work:</b> <span>{selected ? selected.worktype : "-"}</span></p>
                            <p><b>Approving Person:</b> <span>{selected ? selected.approval : "-"}</span></p>
                            <p><b>Date Needed:</b> <span>{selected ? selected.dateneeded : "-"}</span></p>
                            <div className="request-reference-block">
                                <p><b>Reference File:</b></p>
                                {selected && selected.hasReferenceFile && selected.referenceFileUrl ? (
                                    <div className="request-reference-content">
                                        {selected.referenceIsImage ? (
                                            <img src={selected.referenceFileUrl} alt={selected.referenceFileName || "Request reference"} className="request-reference-image" />
                                        ) : selected.referenceIsVideo ? (
                                            <video className="request-reference-video" controls src={selected.referenceFileUrl}>
                                                Your browser does not support video preview.
                                            </video>
                                        ) : (
                                            <div className="request-reference-file">{selected.referenceFileName || "Attached file uploaded."}</div>
                                        )}
                                        <small className="request-reference-name">{selected.referenceFileName || ""}</small>
                                    </div>
                                ) : (
                                    <span className="request-reference-empty">No reference file uploaded.</span>
                                )}
                            </div>
                        </div>

                        <div className="preview-col">
                            <h4>DESCRIPTION</h4>
                            <p className="preview-text">{selected ? selected.description : "Click any row in the table to see full details here."}</p>
                        </div>

                        <div className="preview-col">
                            <h4>REQUEST STATUS</h4>
                            <p><b>Date Updated:</b> <span>{selected ? selected.dateupdated : "-"}</span></p>
                            <p><b>Verified By:</b> <span>{selected ? selected.verifiedby : "-"}</span></p>
                            <p><b>Verified Date:</b> <span>{selected ? selected.verifieddate : "-"}</span></p>

                            {canRequestAction ? (
                                isSuperadminView && canRequestVerificationFields ? (
                                    <div className="verifier-sections">
                                        <form
                                            method="post"
                                            action={buildUrl(data.urls.updateTemplate, selected ? selected.requestno : 0)}
                                            onSubmit={onSaveStatusSubmit}
                                            className="verifier-panel"
                                        >
                                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                            <input type="hidden" name="update_scope" value="assignment" />
                                            {!canEditOperationalFields ? (
                                                <input type="hidden" name="status" value={selected ? (selected.status || "") : ""} />
                                            ) : null}
                                            <div className="verifier-grid">
                                                {canEditOperationalFields ? (
                                                    <>
                                                        <label htmlFor="pv-schedule">Scheduled Date</label>
                                                        <input
                                                            id="pv-schedule"
                                                            type="date"
                                                            name="dateneeded"
                                                            className="preview-input"
                                                            value={selectedScheduleDate}
                                                            onChange={(event) => setSelectedScheduleDate(event.target.value)}
                                                            disabled={!selected || !canEditSchedule || isReadOnlyStatus}
                                                        />

                                                        <label htmlFor="pv-personnel">Personnel</label>
                                                        <select
                                                            id="pv-personnel"
                                                            name="personnel"
                                                            className="preview-input"
                                                            value={personnelValue}
                                                            onChange={(event) => setSelectedPersonnel(event.target.value)}
                                                            disabled={!selected || isReadOnlyStatus}
                                                        >
                                                            <option value="">UNASSIGNED</option>
                                                            {personnelOptions.map((name) => (
                                                                <option key={name} value={name}>{name}</option>
                                                            ))}
                                                        </select>

                                                        <label htmlFor="pv-status">Status</label>
                                                        <select
                                                            id="pv-status"
                                                            name="status"
                                                            className="preview-input"
                                                            value={safeStatusValue}
                                                            onChange={(event) => setSelectedStatus(event.target.value)}
                                                            disabled={!selected || isReadOnlyStatus}
                                                        >
                                                            <option value="">Select Status</option>
                                                            {allowedStatusOptions.map((status) => (
                                                                <option key={status} value={status}>{status}</option>
                                                            ))}
                                                        </select>

                                                        <label htmlFor="pv-notes">Notes</label>
                                                        <textarea
                                                            id="pv-notes"
                                                            name="notes"
                                                            className="preview-input notes-box"
                                                            rows="2"
                                                            value={selectedNotes}
                                                            onChange={(event) => setSelectedNotes(event.target.value)}
                                                            disabled={!selected || isReadOnlyStatus}
                                                        />
                                                    </>
                                                ) : null}

                                                {awaitingAdminApproval ? (
                                                    <>
                                                        <label>Status</label>
                                                        <input
                                                            className="preview-input"
                                                            value="Waiting for admin/superadmin approval"
                                                            readOnly
                                                        />
                                                    </>
                                                ) : null}
                                            </div>
                                            <div className="preview-actions">
                                                <button type="submit" className="btn btn-mini" disabled={!selected || (canRequestOperations && isReadOnlyStatus) || awaitingAdminApproval}>Save Assignment</button>
                                            </div>
                                        </form>

                                        <form
                                            method="post"
                                            action={buildUrl(data.urls.updateTemplate, selected ? selected.requestno : 0)}
                                            onSubmit={onSaveVerificationSubmit}
                                            className="verifier-panel"
                                        >
                                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                            <input type="hidden" name="update_scope" value="verification" />
                                            <input type="hidden" name="status" value={safeStatusValue} />
                                            <div className="verifier-grid">
                                                <label htmlFor="pv-findings">Findings</label>
                                                <select
                                                    id="pv-findings"
                                                    name="findings"
                                                    className="preview-input"
                                                    value={findingsValue}
                                                    onChange={(event) => setSelectedFindings(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                >
                                                    <option value="">Select Findings</option>
                                                    {findingsOptions.map((item) => (
                                                        <option key={item} value={item}>{item}</option>
                                                    ))}
                                                </select>

                                                <label htmlFor="pv-verifiednote">Verified Note</label>
                                                <textarea
                                                    id="pv-verifiednote"
                                                    name="verifiednote"
                                                    className="preview-input notes-box"
                                                    rows="2"
                                                    value={selectedVerifiedNote}
                                                    onChange={(event) => setSelectedVerifiedNote(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                />

                                                <label htmlFor="pv-auto-verifiedby">Verified By</label>
                                                <input
                                                    id="pv-auto-verifiedby"
                                                    className="preview-input"
                                                    value={currentApproverName || "-"}
                                                    readOnly
                                                />
                                            </div>
                                            <div className="preview-actions">
                                                <button type="submit" className="btn btn-mini" disabled={!selected || isReadOnlyStatus}>Save Verification</button>
                                            </div>
                                        </form>
                                    </div>
                                ) : (
                                <form method="post" action={buildUrl(data.urls.updateTemplate, selected ? selected.requestno : 0)} onSubmit={onSaveStatusSubmit}>
                                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                    <input type="hidden" name="update_scope" value="all" />
                                    {!canEditOperationalFields ? (
                                        <input type="hidden" name="status" value={selected ? (selected.status || "") : ""} />
                                    ) : null}
                                    <div className="verifier-grid">
                                        {canEditOperationalFields ? (
                                            <>
                                                <label htmlFor="pv-schedule">Scheduled Date</label>
                                                <input
                                                    id="pv-schedule"
                                                    type="date"
                                                    name="dateneeded"
                                                    className="preview-input"
                                                    value={selectedScheduleDate}
                                                    onChange={(event) => setSelectedScheduleDate(event.target.value)}
                                                    disabled={!selected || !canEditSchedule || isReadOnlyStatus}
                                                />

                                                <label htmlFor="pv-personnel">Personnel</label>
                                                <select
                                                    id="pv-personnel"
                                                    name="personnel"
                                                    className="preview-input"
                                                    value={personnelValue}
                                                    onChange={(event) => setSelectedPersonnel(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                >
                                                    <option value="">UNASSIGNED</option>
                                                    {personnelOptions.map((name) => (
                                                        <option key={name} value={name}>{name}</option>
                                                    ))}
                                                </select>

                                                <label htmlFor="pv-status">Status</label>
                                                <select
                                                    id="pv-status"
                                                    name="status"
                                                    className="preview-input"
                                                    value={safeStatusValue}
                                                    onChange={(event) => setSelectedStatus(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                >
                                                    <option value="">Select Status</option>
                                                    {allowedStatusOptions.map((status) => (
                                                        <option key={status} value={status}>{status}</option>
                                                    ))}
                                                </select>

                                                <label htmlFor="pv-notes">Notes</label>
                                                <textarea
                                                    id="pv-notes"
                                                    name="notes"
                                                    className="preview-input notes-box"
                                                    rows="2"
                                                    value={selectedNotes}
                                                    onChange={(event) => setSelectedNotes(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                />
                                            </>
                                        ) : null}

                                        {awaitingAdminApproval ? (
                                            <>
                                                <label>Status</label>
                                                <input
                                                    className="preview-input"
                                                    value="Waiting for admin/superadmin approval"
                                                    readOnly
                                                />
                                            </>
                                        ) : null}

                                        {canRequestVerificationFields ? (
                                            <>
                                                <label htmlFor="pv-findings">Findings</label>
                                                <select
                                                    id="pv-findings"
                                                    name="findings"
                                                    className="preview-input"
                                                    value={findingsValue}
                                                    onChange={(event) => setSelectedFindings(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                >
                                                    <option value="">Select Findings</option>
                                                    {findingsOptions.map((item) => (
                                                        <option key={item} value={item}>{item}</option>
                                                    ))}
                                                </select>

                                                <label htmlFor="pv-verifiednote">Verified Note</label>
                                                <textarea
                                                    id="pv-verifiednote"
                                                    name="verifiednote"
                                                    className="preview-input notes-box"
                                                    rows="2"
                                                    value={selectedVerifiedNote}
                                                    onChange={(event) => setSelectedVerifiedNote(event.target.value)}
                                                    disabled={!selected || isReadOnlyStatus}
                                                />

                                                <label htmlFor="pv-auto-verifiedby">Verified By</label>
                                                <input
                                                    id="pv-auto-verifiedby"
                                                    className="preview-input"
                                                    value={currentApproverName || "-"}
                                                    readOnly
                                                />
                                            </>
                                        ) : null}
                                    </div>
                                    <div className="preview-actions">
                                        <button type="submit" className="btn btn-mini" disabled={!selected || (canRequestOperations && isReadOnlyStatus) || awaitingAdminApproval}>Save Status</button>
                                    </div>
                                </form>
                                )
                            ) : (
                                <>
                                    <p><b>Personnel:</b> <span>{selected ? selected.personnel : "-"}</span></p>
                                    <p><b>Status:</b> <span>{selected ? selected.status : "-"}</span></p>
                                    <p><b>Notes:</b> <span>{selected ? selected.notes : "-"}</span></p>
                                    <p><b>Findings:</b> <span>{selected ? selected.findings : "-"}</span></p>
                                    <p><b>Verified Note:</b> <span>{selected ? selected.verifiednote : "-"}</span></p>
                                </>
                            )}
                            {data.permissions.canRequestDelete ? (
                                <div className="preview-actions">
                                    <form
                                        method="post"
                                        action={buildUrl(data.urls.deleteTemplate, selected ? selected.requestno : 0)}
                                        onSubmit={onDeleteSubmit}
                                    >
                                        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                        <button type="submit" className="btn btn-mini btn-danger" disabled={!selected}>Delete</button>
                                    </form>
                                </div>
                            ) : null}
                        </div>
                    </div>
                </section>
                <ConfirmDialog
                    open={Boolean(deleteForm)}
                    title="Delete Request"
                    message="Are you sure you want to delete this request?"
                    confirmLabel="Delete"
                    confirmClassName="btn btn-danger"
                    onCancel={closeDeleteModal}
                    onConfirm={confirmDelete}
                />
                <ConfirmDialog
                    open={Boolean(warningMessage)}
                    title="Incomplete Details"
                    message={warningMessage}
                    confirmLabel="OK"
                    confirmClassName="btn btn-primary"
                    onCancel={closeWarningModal}
                    onConfirm={closeWarningModal}
                />
            </>
        );
    }

    function RequestsPage({ data }) {
        return (
            <section className="page-card request-explorer">
                {data.isUserRequestMode ? <UserRequestMode data={data} /> : <AdminRequestMode data={data} />}
            </section>
        );
    }

    function ProfilePage({ data }) {
        const user = data.user || {};
        return (
            <section className="page-card profile-page">
                <header className="page-header split">
                    <h1>PROFILE SETTINGS</h1>
                    <span className="subtitle">Manage your account</span>
                </header>

                <div className="profile-grid">
                    <section className="panel-card profile-card">
                        <div className="profile-hero">
                            {data.profileImageData ? (
                                <img src={data.profileImageData} alt="Profile image" className="profile-avatar" />
                            ) : (
                                <div className="profile-avatar profile-avatar-fallback">{data.profileInitial}</div>
                            )}
                            <div>
                                <h2>{user.name || ""}</h2>
                                <p>@{user.username || ""}</p>
                                <small>{user.position || ""} · {user.status || ""}</small>
                            </div>
                        </div>

                        <form method="post" encType="multipart/form-data" className="crud-form">
                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                            <input type="hidden" name="action" value="profile" />
                            {data.profileFormFields.map((field) => (
                                <GenericField key={field.name} field={field} />
                            ))}
                            <div className="form-actions">
                                <button type="submit" className="btn btn-primary">Save Profile</button>
                            </div>
                        </form>
                    </section>

                    <section className="panel-card profile-card">
                        <h3>Change Password</h3>
                        <form method="post" className="crud-form">
                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                            <input type="hidden" name="action" value="password" />
                            {data.passwordFormFields.map((field) => (
                                <GenericField key={field.name} field={field} />
                            ))}
                            <div className="form-actions">
                                <button type="submit" className="btn btn-primary">Update Password</button>
                            </div>
                        </form>

                        <div className="profile-readonly">
                            <h3>Account Details</h3>
                            <div className="profile-readonly-grid">
                                <span>User ID</span><strong>{user.userid}</strong>
                                <span>Name</span><strong>{user.name}</strong>
                                <span>Username</span><strong>{user.username}</strong>
                                <span>Department</span><strong>{user.department}</strong>
                                <span>Address</span><strong>{user.address}</strong>
                                <span>Contact</span><strong>{user.contact}</strong>
                                <span>Position</span><strong>{user.position}</strong>
                                <span>Status</span><strong>{user.status}</strong>
                            </div>
                        </div>
                    </section>
                </div>
            </section>
        );
    }

    function PageContent({ type, data }) {
        if (type === "dashboard") {
            return <DashboardPage data={data} />;
        }
        if (type === "entity") {
            return <EntityPage data={data} />;
        }
        if (type === "requests") {
            return <RequestsPage data={data} />;
        }
        if (type === "profile") {
            return <ProfilePage data={data} />;
        }
        return (
            <section className="page-card">
                <header className="page-header">
                    <h1>UNKNOWN PAGE</h1>
                </header>
            </section>
        );
    }

    function AppShell({ shell, page, type }) {
        const [showLogoutModal, setShowLogoutModal] = React.useState(false);
        const sections = shell.menuSections || [];
        const messageItems = shell.messages || [];
        const activePage = shell.activePage || "";

        function onLogoutClick(event) {
            event.preventDefault();
            setShowLogoutModal(true);
        }

        function closeModal() {
            setShowLogoutModal(false);
        }

        function confirmLogout() {
            window.location.href = shell.logoutUrl;
        }

        React.useEffect(() => {
            function onEscape(event) {
                if (event.key === "Escape") {
                    closeModal();
                }
            }
            document.addEventListener("keydown", onEscape);
            return () => document.removeEventListener("keydown", onEscape);
        }, []);

        return (
            <>
                <div className="app-shell">
                    <aside className="sidebar">
                        <div className="brand-block">
                            <div className="brand-title">Sagrex Foods</div>
                            <div className="brand-subtitle">Machine Work RF</div>
                        </div>

                        <nav className="menu">
                            {sections.map((section) => (
                                <React.Fragment key={section.heading}>
                                    <div className="menu-heading">{section.heading}</div>
                                    {(section.items || []).map((item) => (
                                        <a
                                            key={item.key}
                                            href={item.url}
                                            className={`menu-item ${activePage === item.key ? "active" : ""}`}
                                        >
                                            {item.label}
                                        </a>
                                    ))}
                                </React.Fragment>
                            ))}
                        </nav>

                        <div className="sidebar-footer">
                            <span>{(shell.currentUser || {}).name || "Super Admin"}</span>
                            <a href={shell.logoutUrl} onClick={onLogoutClick}>Logout</a>
                        </div>
                    </aside>

                    <main className="main-panel">
                        {messageItems.length ? (
                            <div className="messages">
                                {messageItems.map((message, idx) => (
                                    <div className="message" key={`message-${idx}`}>{message}</div>
                                ))}
                            </div>
                        ) : null}
                        <PageContent type={type} data={page} />
                    </main>
                </div>

                {showLogoutModal ? (
                    <div className="logout-modal">
                        <div className="logout-backdrop" onClick={closeModal}></div>
                        <div className="logout-dialog" role="dialog" aria-modal="true" aria-labelledby="logoutTitle">
                            <h3 id="logoutTitle">Confirm Logout</h3>
                            <p>Are you sure you want to logout?</p>
                            <div className="logout-actions">
                                <button type="button" className="btn" onClick={closeModal}>Cancel</button>
                                <button type="button" className="btn btn-primary" onClick={confirmLogout}>Logout</button>
                            </div>
                        </div>
                    </div>
                ) : null}
            </>
        );
    }

    const root = document.getElementById("coreReactRoot");
    if (root) {
        ReactDOM.createRoot(root).render(<AppShell shell={shellData} page={pageData} type={pageType} />);
    }
})();
