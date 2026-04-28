import React from "react";
import { createRoot } from "react-dom/client";

const cfg = window.LOGIN_CONFIG || {};
const initialErrorMessage = cfg.initialError || "";

function UserIcon() {
    return (
        <svg className="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <circle cx="12" cy="8" r="5"></circle>
            <rect x="3.5" y="13.6" width="17" height="9.2" rx="4.4"></rect>
        </svg>
    );
}

function LockIcon() {
    return (
        <svg className="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M8.2 10.2V7.8a3.8 3.8 0 1 1 7.6 0v2.4h1.5c1.3 0 2.3 1 2.3 2.3V20c0 1.3-1 2.3-2.3 2.3H6.7c-1.3 0-2.3-1-2.3-2.3v-7.5c0-1.3 1-2.3 2.3-2.3h1.5Zm5 5.1c0-.7-.5-1.2-1.2-1.2s-1.2.5-1.2 1.2c0 .5.3.9.7 1.1v2.2h1v-2.2c.4-.2.7-.6.7-1.1Zm1-5.1V7.8a2.2 2.2 0 1 0-4.4 0v2.4h4.4Z"></path>
        </svg>
    );
}

function GoldenSabaBadge({ className = "badge-image" }) {
    return <img className={className} src={cfg.goldenSabaLogoUrl} alt="Golden Saba logo" />;
}

function LoginPage() {
    const [username, setUsername] = React.useState("");
    const [password, setPassword] = React.useState("");
    const [errorMessage, setErrorMessage] = React.useState(initialErrorMessage);
    const [submitting, setSubmitting] = React.useState(false);

    const onSubmit = async (event) => {
        event.preventDefault();
        setErrorMessage("");

        if (!username.trim() || !password.trim()) {
            setErrorMessage("Username and password are required.");
            return;
        }

        setSubmitting(true);
        try {
            const response = await fetch(cfg.loginApiUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: username.trim(),
                    password,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                setErrorMessage(data.message || "Login failed.");
                return;
            }
            if (data.access_token) {
                localStorage.setItem("mwrf_access_token", data.access_token);
            }
            window.location.href = data.redirect || cfg.dashboardUrl;
        } catch (error) {
            setErrorMessage("Unable to connect to server.");
        } finally {
            setSubmitting(false);
        }
    };

    const onClear = () => {
        setUsername("");
        setPassword("");
        setErrorMessage("");
    };

    return (
        <main className="page">
            <section className="card">
                <header className="hero">
                    <div className="hero-brand">
                        <div className="logo-tile">
                            <img className="logo-image" src={cfg.sfiLogoUrl} alt="SFI logo" />
                        </div>
                        <GoldenSabaBadge className="hero-saba" />
                    </div>
                </header>

                <section className="info-box"></section>

                <form className="form-area" onSubmit={onSubmit}>
                    <div className="field-group">
                        <label htmlFor="username">USERNAME</label>
                        <div className="input-shell">
                            <UserIcon />
                            <input
                                id="username"
                                type="text"
                                placeholder="Enter your Username"
                                value={username}
                                onChange={(event) => setUsername(event.target.value)}
                                autoComplete="username"
                            />
                        </div>
                    </div>

                    <div className="field-group">
                        <label htmlFor="password">PASSWORD</label>
                        <div className="input-shell">
                            <LockIcon />
                            <input
                                id="password"
                                type="password"
                                placeholder="Enter your Password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                autoComplete="current-password"
                            />
                        </div>
                    </div>

                    <div className="button-row">
                        <button type="submit" className="sign-in-btn" disabled={submitting}>
                            {submitting ? "Signing In..." : "Sign In"}
                        </button>
                        <button type="button" className="clear-btn" onClick={onClear}>Clear</button>
                    </div>
                    {errorMessage && <p className="login-error">{errorMessage}</p>}

                    <div className="links">
                        <a href="#">Forgot username or password?</a>
                        <a href={cfg.registerUrl}>Don't have an account? Register</a>
                    </div>
                </form>
            </section>
        </main>
    );
}

const root = document.getElementById("root");
if (root) {
    createRoot(root).render(<LoginPage />);
}

