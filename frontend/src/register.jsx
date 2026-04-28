import React from "react";
import { createRoot } from "react-dom/client";

const cfg = window.REGISTER_CONFIG || {};
const departments = cfg.departments || [];

function RegisterPage() {
    const [form, setForm] = React.useState({
        fullname: "",
        department: departments[0] || "",
        address: "",
        contact: "",
        password: "",
        consent: false,
    });
    const [error, setError] = React.useState("");
    const [success, setSuccess] = React.useState("");
    const [saving, setSaving] = React.useState(false);

    const updateField = (key, value) => {
        setForm((prev) => ({ ...prev, [key]: value }));
    };

    const clearForm = () => {
        setForm({
            fullname: "",
            department: departments[0] || "",
            address: "",
            contact: "",
            password: "",
            consent: false,
        });
        setError("");
        setSuccess("");
    };

    const onSubmit = async (event) => {
        event.preventDefault();
        setError("");
        setSuccess("");

        if (!form.fullname || !form.department || !form.address || !form.contact || !form.password) {
            setError("All fields are required.");
            return;
        }
        if (form.password.length < 6) {
            setError("Password must be at least 6 characters.");
            return;
        }
        if (!form.consent) {
            setError("Please accept the privacy consent first.");
            return;
        }

        setSaving(true);
        try {
            const response = await fetch(cfg.registerApiUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                setError(data.message || "Registration failed.");
                return;
            }
            setSuccess(`${data.message} Username: ${data.username}`);
            clearForm();
        } catch (err) {
            setError("Unable to connect to server.");
        } finally {
            setSaving(false);
        }
    };

    return (
        <main className="page">
            <section className="card">
                <header className="hero">
                    <div className="hero-brand">
                        <div className="logo-tile">
                            <img className="logo-image" src={cfg.sfiLogoUrl} alt="SFI logo" />
                        </div>
                        <img className="hero-saba" src={cfg.goldenSabaLogoUrl} alt="Golden Saba logo" />
                    </div>
                </header>

                <form className="form-wrap" onSubmit={onSubmit}>
                    <div className="field-grid">
                        <label htmlFor="fullname">Full Name</label>
                        <input
                            id="fullname"
                            value={form.fullname}
                            onChange={(e) => updateField("fullname", e.target.value)}
                            maxLength={50}
                        />

                        <label htmlFor="department">Department</label>
                        <select
                            id="department"
                            value={form.department}
                            onChange={(e) => updateField("department", e.target.value)}
                        >
                            {departments.length === 0 && <option value="">No departments found</option>}
                            {departments.map((dep) => (
                                <option key={dep} value={dep}>{dep}</option>
                            ))}
                        </select>

                        <label htmlFor="address">Address</label>
                        <input
                            id="address"
                            value={form.address}
                            onChange={(e) => updateField("address", e.target.value)}
                            maxLength={25}
                        />

                        <label htmlFor="contact">Contact</label>
                        <input
                            id="contact"
                            value={form.contact}
                            onChange={(e) => updateField("contact", e.target.value)}
                            maxLength={15}
                        />

                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            value={form.password}
                            onChange={(e) => updateField("password", e.target.value)}
                            minLength={6}
                            maxLength={50}
                            autoComplete="new-password"
                        />

                        <label htmlFor="role">Role</label>
                        <input id="role" className="readonly" value="USER" readOnly />

                        <label htmlFor="status">Status</label>
                        <input id="status" className="readonly" value="INACTIVE" readOnly />
                    </div>

                    <div className="actions">
                        <button type="submit" className="btn-save" disabled={saving}>
                            {saving ? "Saving..." : "Save"}
                        </button>
                        <button type="button" onClick={clearForm}>Clear</button>
                    </div>

                    <label className="consent">
                        <input
                            type="checkbox"
                            checked={form.consent}
                            onChange={(e) => updateField("consent", e.target.checked)}
                        />
                        <span>
                            I have read about the Data Privacy Statement as well as the SFI Centralized System
                            Privacy Policy and expressly consent to processing my personal data for system
                            operation and records management.
                        </span>
                    </label>

                    {error && <p className="error">{error}</p>}
                    {success && <p className="success">{success}</p>}

                    <div className="bottom-link">
                        <a href={cfg.loginUrl}>Back to Login</a>
                    </div>
                </form>
            </section>
        </main>
    );
}

const root = document.getElementById("root");
if (root) {
    createRoot(root).render(<RegisterPage />);
}

