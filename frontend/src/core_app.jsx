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
            { label: "DONE", value: data.counts.done, tone: "green" },
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
                    {data.formFields.map((field, index) => (
                        <React.Fragment key={`${field.name}-${index}`}>
                            {isUsersEntity && field.name === "username" ? (
                                <h4 className="form-section-title">Create Login Account</h4>
                            ) : null}
                            {renderField(field, index)}
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
        const ongoingRows = data.ongoingRecords || [];

        return (
            <>
                <section className="user-request-entry">
                    <form method="post" encType="multipart/form-data" className="user-request-form">
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
                                <UserRequestField field={fields.requestdept} label="Requested Dept" />
                            </div>

                            <div className="user-form-col">
                                <UserRequestField field={fields.machinegroup} label="Machine Group" />
                                <UserRequestField field={fields.worktype} label="Type of Work" />
                                <UserRequestField field={fields.approval} label="Approving Person" />
                                <UserRequestField field={fields.dateneeded} label="Date Needed" />
                            </div>

                            <div className="user-form-col">
                                <UserRequestField field={fields.description} label="Description" />
                                <UserRequestField field={fields.reference_file} label="Upload File for Reference" />
                            </div>
                        </div>

                        <div className="user-request-bottom-grid">
                            <section className="user-readonly-card">
                                <h4>REQUEST STATUS</h4>
                                <UserRequestField field={fields.personnel} label="Personnel" />
                                <UserRequestField field={fields.status} label="Status" />
                                <UserRequestField field={fields.notes} label="Notes" />
                                <UserRequestField field={fields.dateupdated} label="Date Updated" />
                            </section>

                            <section className="user-readonly-card">
                                <h4>WORK REQUEST VERIFIER</h4>
                                <UserRequestField field={fields.verifiedby} label="Verified by" />
                                <UserRequestField field={fields.findings} label="Findings" />
                                <UserRequestField field={fields.verifiednote} label="Notes" />
                                <UserRequestField field={fields.verifieddate} label="Date Updated" />
                            </section>

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

                <section className="user-ongoing-panel">
                    <div className="user-ongoing-head">
                        <h3>ONGOING REQUESTS</h3>
                        <a href={data.urls.onGoingFilter} className="btn btn-mini">View On-going Page</a>
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
                                {ongoingRows.length === 0 ? (
                                    <tr>
                                        <td colSpan="5" className="empty">No ongoing requests.</td>
                                    </tr>
                                ) : (
                                    ongoingRows.map((row) => (
                                        <tr key={`ongoing-${row.requestno}`}>
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
        );
    }

    function AdminRequestMode({ data }) {
        const [showNewRequest, setShowNewRequest] = React.useState(false);
        const [selectedRequestNo, setSelectedRequestNo] = React.useState(
            data.records.length ? data.records[0].requestno : null
        );
        const [deleteForm, setDeleteForm] = React.useState(null);

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
                <header className="request-toolbar">
                    <h1>{data.filterLabel}</h1>
                    <form method="get" className="request-search">
                        <input type="text" name="q" placeholder="Search requests..." defaultValue={data.query || ""} />
                        <button type="submit">Search</button>
                    </form>
                    {data.permissions.canRequestCreate ? (
                        <button
                            type="button"
                            className="btn btn-primary"
                            onClick={() => setShowNewRequest((prev) => !prev)}
                        >
                            + New Request
                        </button>
                    ) : null}
                </header>

                {data.permissions.canRequestCreate && showNewRequest ? (
                    <section className="new-request-panel">
                        <h3>Create New Request</h3>
                        <form method="post" className="crud-form">
                            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                            <div className="request-form-grid">
                                {data.formFields.map((field) => (
                                    <GenericField key={field.name} field={field} />
                                ))}
                            </div>
                            <div className="form-actions">
                                <button type="submit" className="btn btn-primary">Create Request</button>
                            </div>
                        </form>
                    </section>
                ) : null}

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
                        </div>

                        <div className="preview-col">
                            <h4>DESCRIPTION</h4>
                            <p className="preview-text">{selected ? selected.description : "Click any row in the table to see full details here."}</p>
                        </div>

                        <div className="preview-col">
                            {data.isDoneFilter ? (
                                <>
                                    <h4>WORK REQUEST VERIFIER</h4>
                                    <div className="verifier-grid">
                                        <label htmlFor="pv-verifiedby">Verified by</label>
                                        <input id="pv-verifiedby" className="preview-input" value={selected ? selected.verifiedby : "-"} readOnly />

                                        <label htmlFor="pv-findings">Findings</label>
                                        <select id="pv-findings" className="preview-input" disabled value={selected ? selected.findings : "-"}>
                                            <option value={selected ? selected.findings : "-"}>{selected ? selected.findings : "-"}</option>
                                        </select>

                                        <label htmlFor="pv-verifiednote">Notes</label>
                                        <textarea id="pv-verifiednote" className="preview-input notes-box" rows="3" value={selected ? selected.verifiednote : "-"} readOnly />

                                        <label htmlFor="pv-dateupdated">Date Updated</label>
                                        <input id="pv-dateupdated" className="preview-input" value={selected ? selected.dateupdated : "-"} readOnly />
                                    </div>
                                </>
                            ) : (
                                <>
                                    <h4>REQUEST STATUS</h4>
                                    <p><b>Personnel:</b> <span>{selected ? selected.personnel : "-"}</span></p>
                                    <p><b>Status:</b> <span>{selected ? selected.status : "-"}</span></p>
                                    <p><b>Notes:</b> <span>{selected ? selected.notes : "-"}</span></p>
                                    <p><b>Date Updated:</b> <span>{selected ? selected.dateupdated : "-"}</span></p>
                                    <p><b>Verified By:</b> <span>{selected ? selected.verifiedby : "-"}</span></p>
                                    <p><b>Findings:</b> <span>{selected ? selected.findings : "-"}</span></p>
                                    <p><b>Verified Note:</b> <span>{selected ? selected.verifiednote : "-"}</span></p>

                                    {data.permissions.canRequestAction || data.permissions.canRequestDelete ? (
                                        <div className="preview-actions">
                                            {data.permissions.canRequestAction ? (
                                                <>
                                                    <form method="post" action={buildUrl(data.urls.verifyTemplate, selected ? selected.requestno : 0)}>
                                                        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                                        <button type="submit" className="btn btn-mini" disabled={!selected}>Verify</button>
                                                    </form>
                                                    <form method="post" action={buildUrl(data.urls.rejectTemplate, selected ? selected.requestno : 0)}>
                                                        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                                        <button type="submit" className="btn btn-mini" disabled={!selected}>Reject</button>
                                                    </form>
                                                    <form method="post" action={buildUrl(data.urls.backjobTemplate, selected ? selected.requestno : 0)}>
                                                        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                                        <button type="submit" className="btn btn-mini" disabled={!selected}>Backjob</button>
                                                    </form>
                                                </>
                                            ) : null}
                                            {data.permissions.canRequestDelete ? (
                                                <form
                                                    method="post"
                                                    action={buildUrl(data.urls.deleteTemplate, selected ? selected.requestno : 0)}
                                                    onSubmit={onDeleteSubmit}
                                                >
                                                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                                                    <button type="submit" className="btn btn-mini btn-danger" disabled={!selected}>Delete</button>
                                                </form>
                                            ) : null}
                                        </div>
                                    ) : null}
                                </>
                            )}
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
