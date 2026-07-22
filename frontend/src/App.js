import React, { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import "./App.css";
import Notification from "./Notification";

const API_BASE_URL =
  process.env.REACT_APP_API_URL || "https://karabala10.pythonanywhere.com/api";

/** Same-tab refresh keeps Google session until Sign out or token revoked (sessionStorage). */
const STORAGE_GOOGLE_TOKEN = "cv_mailer_google_access_token";
const STORAGE_GOOGLE_USER = "cv_mailer_google_user";
/** Form fields persist across reloads (localStorage); the CV file is never stored. */
const STORAGE_FORM = "cv_mailer_form_v1";
const STORAGE_THEME = "cv_mailer_theme";

const DEFAULT_MAX_PDF_BYTES = 15 * 1024 * 1024;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const isValidEmail = (email) => EMAIL_RE.test((email || "").trim());

const formatBytes = (bytes) => {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
};

const loadStoredForm = () => {
  try {
    const raw = localStorage.getItem(STORAGE_FORM);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
};

const getInitialTheme = () => {
  try {
    const stored = localStorage.getItem(STORAGE_THEME);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* ignore */
  }
  if (
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    return "dark";
  }
  return "light";
};

/** Parse pasted / CSV text into recipients. Accepts comma, tab or semicolon delimiters. */
const parseRecipientsText = (text) => {
  const out = [];
  const seen = new Set();
  (text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const parts = line.split(/[,;\t]/).map((p) => p.trim());
      const email = parts[0] || "";
      const company = parts.slice(1).join(" ").trim();
      if (!isValidEmail(email)) return;
      const key = email.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push({ email, company });
    });
  return out;
};

function App() {
  const storedForm = useMemo(loadStoredForm, []);

  const [recipients, setRecipients] = useState(
    Array.isArray(storedForm.recipients) && storedForm.recipients.length
      ? storedForm.recipients
      : [{ email: "", company: "" }],
  );
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [oauthAccessToken, setOauthAccessToken] = useState("");
  /**
   * Google profile: undefined = signed out, null = loading userinfo, object = result.
   */
  const [googleUser, setGoogleUser] = useState(undefined);
  const [googleOAuthReady, setGoogleOAuthReady] = useState(false);
  const [jobTitle, setJobTitle] = useState(storedForm.jobTitle || "");
  const [subject, setSubject] = useState(storedForm.subject || "");
  // Once the user edits the subject, stop auto-deriving it from the name.
  const [subjectEdited, setSubjectEdited] = useState(
    storedForm.subjectEdited !== undefined
      ? Boolean(storedForm.subjectEdited)
      : Boolean((storedForm.subject || "").trim()),
  );
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfFileName, setPdfFileName] = useState("");
  const [name, setName] = useState(storedForm.name || "");
  const [phoneNumber, setPhoneNumber] = useState(storedForm.phoneNumber || "");
  const [portfolioLink, setPortfolioLink] = useState(
    storedForm.portfolioLink || "",
  );
  const [notification, setNotification] = useState({
    show: false,
    message: "",
    type: "info",
  });
  const [recipientStatus, setRecipientStatus] = useState({});
  const [showPreview, setShowPreview] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [sendProgress, setSendProgress] = useState({ current: 0, total: 0 });
  const [testSending, setTestSending] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [theme, setTheme] = useState(getInitialTheme);
  const [showSignInModal, setShowSignInModal] = useState(false);

  const maxPdfBytes = config?.max_pdf_bytes || DEFAULT_MAX_PDF_BYTES;

  const canPreviewEmail = Boolean(
    name.trim() && jobTitle.trim() && phoneNumber.trim(),
  );

  useEffect(() => {
    fetchConfig();
  }, []);

  // Persist form fields (never the CV file itself).
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_FORM,
        JSON.stringify({
          name,
          jobTitle,
          subject,
          subjectEdited,
          phoneNumber,
          portfolioLink,
          recipients,
        }),
      );
    } catch {
      /* ignore quota / private-mode errors */
    }
  }, [
    name,
    jobTitle,
    subject,
    subjectEdited,
    phoneNumber,
    portfolioLink,
    recipients,
  ]);

  // Auto-derive the subject from the name until the user edits it manually.
  useEffect(() => {
    if (subjectEdited) return;
    setSubject(name.trim() ? `Job Application - ${name.trim()}` : "");
  }, [name, subjectEdited]);

  // Apply + persist theme.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(STORAGE_THEME, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  useEffect(() => {
    if (!showPreview && !showImport) {
      return;
    }
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        setShowPreview(false);
        setShowImport(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showPreview, showImport]);

  const googleClientId =
    config?.google_oauth_client_id ||
    process.env.REACT_APP_GOOGLE_OAUTH_CLIENT_ID ||
    "";
  const serverOauthConfigured = Boolean(config?.server_oauth_configured);
  const hasBrowserGoogleToken = Boolean(oauthAccessToken.trim());
  const oauthConfigured = Boolean(googleClientId) || serverOauthConfigured;
  const authReadyForSend =
    (Boolean(googleClientId) && hasBrowserGoogleToken) ||
    (!googleClientId && serverOauthConfigured);
  // Browser sign-in flow: lock the whole app until the user connects Google.
  const mustSignIn = Boolean(googleClientId) && !hasBrowserGoogleToken;

  // Show the sign-in prompt whenever a sign-in is required; hide it once signed in.
  useEffect(() => {
    setShowSignInModal(mustSignIn);
  }, [mustSignIn]);

  useEffect(() => {
    if (!googleClientId) {
      setGoogleOAuthReady(false);
      return;
    }
    let cancelled = false;
    const waitForGoogle = () => {
      if (cancelled) return;
      if (window.google?.accounts?.oauth2) {
        setGoogleOAuthReady(true);
        return;
      }
      setTimeout(waitForGoogle, 50);
    };
    waitForGoogle();
    return () => {
      cancelled = true;
    };
  }, [googleClientId]);

  const clearGoogleSession = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_GOOGLE_TOKEN);
      sessionStorage.removeItem(STORAGE_GOOGLE_USER);
    } catch {
      /* ignore */
    }
    setOauthAccessToken("");
    setGoogleUser(undefined);
  }, []);

  /** @returns {Promise<number>} HTTP status (200 if OK) */
  const fetchGoogleUserProfile = useCallback(
    async (accessToken, { showLoading = true } = {}) => {
      if (showLoading) {
        setGoogleUser(null);
      }
      try {
        const r = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!r.ok) {
          if (showLoading) {
            setGoogleUser({ email: "", name: "", picture: "" });
            try {
              sessionStorage.removeItem(STORAGE_GOOGLE_USER);
            } catch {
              /* ignore */
            }
          }
          return r.status;
        }
        const u = await r.json();
        const profile = {
          email: (u.email || "").trim(),
          name: (u.name || "").trim(),
          picture: (u.picture || "").trim(),
        };
        setGoogleUser(profile);
        // Pre-fill the name from the Google account only when it's still empty,
        // so a returning / edited value is never clobbered.
        if (profile.name) {
          setName((prev) => (prev.trim() ? prev : profile.name));
        }
        try {
          sessionStorage.setItem(STORAGE_GOOGLE_USER, JSON.stringify(profile));
        } catch {
          /* ignore */
        }
        return r.status;
      } catch {
        if (showLoading) {
          setGoogleUser({ email: "", name: "", picture: "" });
          try {
            sessionStorage.removeItem(STORAGE_GOOGLE_USER);
          } catch {
            /* ignore */
          }
        }
        return 0;
      }
    },
    [],
  );

  useEffect(() => {
    if (!googleClientId) {
      return;
    }
    let cancelled = false;
    const token = (() => {
      try {
        return sessionStorage.getItem(STORAGE_GOOGLE_TOKEN)?.trim() || "";
      } catch {
        return "";
      }
    })();
    if (!token) {
      return;
    }

    let cached = null;
    try {
      const raw = sessionStorage.getItem(STORAGE_GOOGLE_USER);
      if (raw) {
        cached = JSON.parse(raw);
      }
    } catch {
      cached = null;
    }

    const hasCachedProfile =
      cached &&
      typeof cached === "object" &&
      (cached.email || cached.name || cached.picture);

    setOauthAccessToken(token);
    if (hasCachedProfile) {
      setGoogleUser(cached);
    }

    void (async () => {
      const status = await fetchGoogleUserProfile(token, {
        showLoading: !hasCachedProfile,
      });
      if (cancelled) {
        return;
      }
      if (status === 401 || status === 403) {
        clearGoogleSession();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [googleClientId, fetchGoogleUserProfile, clearGoogleSession]);

  const requestGoogleAccessToken = () => {
    if (!googleClientId || !window.google?.accounts?.oauth2) {
      showNotification(
        "Google Sign-In is not available yet. Try again.",
        "warning",
      );
      return;
    }
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: googleClientId,
      scope: [
        "https://mail.google.com/",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
      ].join(" "),
      callback: (tokenResponse) => {
        if (tokenResponse.error) {
          showNotification(
            tokenResponse.error_description || tokenResponse.error,
            "error",
          );
          return;
        }
        if (tokenResponse.access_token) {
          const t = tokenResponse.access_token;
          setOauthAccessToken(t);
          try {
            sessionStorage.setItem(STORAGE_GOOGLE_TOKEN, t);
          } catch {
            /* ignore */
          }
          void fetchGoogleUserProfile(t);
          showNotification("Signed in with Google", "success");
        }
      },
    });
    client.requestAccessToken({ prompt: "" });
  };

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/config`);
      setConfig(response.data);
    } catch (error) {
      console.error("Failed to fetch config:", error);
    }
  };

  const addRecipient = () => {
    setRecipients([...recipients, { email: "", company: "" }]);
  };

  const removeRecipient = (index) => {
    setRecipients(recipients.filter((_, i) => i !== index));
  };

  const updateRecipient = (index, field, value) => {
    const updated = [...recipients];
    updated[index][field] = value;
    setRecipients(updated);
  };

  const clearRecipients = () => {
    setRecipients([{ email: "", company: "" }]);
    setRecipientStatus({});
    setResults(null);
  };

  const showNotification = (message, type = "info") => {
    setNotification({ show: true, message, type });
    setTimeout(() => {
      setNotification({ show: false, message: "", type: "info" });
    }, 5000);
  };

  const acceptPdfFile = (file) => {
    if (!file) return;
    if (file.type !== "application/pdf") {
      showNotification("Please select a PDF file", "warning");
      return;
    }
    if (file.size > maxPdfBytes) {
      showNotification(
        `PDF is too large (${formatBytes(file.size)}). Maximum is ${formatBytes(
          maxPdfBytes,
        )}.`,
        "error",
      );
      return;
    }
    setPdfFile(file);
    setPdfFileName(file.name);
  };

  const importRecipients = () => {
    const parsed = parseRecipientsText(importText);
    if (parsed.length === 0) {
      showNotification(
        "No valid email addresses found. Use one per line: email, company",
        "warning",
      );
      return;
    }
    setRecipients((prev) => {
      const existing = new Map(
        prev
          .filter((r) => r.email.trim())
          .map((r) => [r.email.trim().toLowerCase(), r]),
      );
      parsed.forEach((r) => {
        existing.set(r.email.toLowerCase(), r);
      });
      const merged = Array.from(existing.values());
      return merged.length ? merged : [{ email: "", company: "" }];
    });
    setImportText("");
    setShowImport(false);
    showNotification(`Imported ${parsed.length} recipient(s)`, "success");
  };

  const openEmailPreview = async () => {
    if (!canPreviewEmail) {
      return;
    }
    setPreviewLoading(true);
    try {
      const firstWithCompany = recipients.find((r) => r.company.trim());
      const response = await axios.post(`${API_BASE_URL}/preview-email`, {
        name: name.trim(),
        job_title: jobTitle.trim(),
        phone_number: phoneNumber.trim().replace(/\D/g, ""),
        portfolio_link: portfolioLink.trim(),
        subject: subject.trim(),
        email:
          (typeof googleUser === "object" && googleUser?.email) ||
          "you@example.com",
        company: firstWithCompany?.company?.trim() || "",
      });
      if (response.data?.html) {
        setPreviewHtml(response.data.html);
        setShowPreview(true);
      } else {
        showNotification("Could not load email preview", "error");
      }
    } catch (error) {
      showNotification(
        `Preview failed: ${error.response?.data?.error || error.message}`,
        "error",
      );
    } finally {
      setPreviewLoading(false);
    }
  };

  /** Shared field/auth checks before any send. Returns true if OK, else notifies. */
  const validateBeforeSend = ({ requireRecipients = true } = {}) => {
    if (requireRecipients) {
      const valid = recipients.filter((r) => r.email.trim() !== "");
      if (valid.length === 0) {
        showNotification(
          "Please add at least one recipient email address",
          "warning",
        );
        return false;
      }
      const invalid = valid.filter((r) => !isValidEmail(r.email));
      if (invalid.length > 0) {
        showNotification(
          `Invalid email address: ${invalid[0].email.trim()}`,
          "warning",
        );
        return false;
      }
    }

    if (googleClientId) {
      if (!oauthAccessToken.trim()) {
        showNotification('Click "Sign in with Google" first.', "warning");
        return false;
      }
    } else if (!serverOauthConfigured) {
      showNotification("Google OAuth is not configured for this app.", "error");
      return false;
    }

    if (!jobTitle.trim()) {
      showNotification("Please enter your job title", "warning");
      return false;
    }
    if (!subject.trim()) {
      showNotification("Please enter email subject", "warning");
      return false;
    }
    if (!pdfFile) {
      showNotification("Please select a PDF file to attach", "warning");
      return false;
    }
    if (!name.trim()) {
      showNotification("Please enter your name", "warning");
      return false;
    }
    if (!phoneNumber.trim()) {
      showNotification("Please enter your phone number", "warning");
      return false;
    }
    return true;
  };

  const readPdfAsBase64 = () =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result.split(",")[1]);
      reader.onerror = () => reject(new Error("Failed to read PDF file"));
      reader.readAsDataURL(pdfFile);
    });

  const commonEmailPayload = (base64Pdf) => {
    const authFields = oauthAccessToken.trim()
      ? { oauth_access_token: oauthAccessToken.trim() }
      : {};
    return {
      sender_email: "",
      ...authFields,
      job_title: jobTitle.trim(),
      subject: subject.trim(),
      pdf_file: base64Pdf,
      pdf_filename: pdfFileName || pdfFile.name,
      name: name.trim(),
      phone_number: phoneNumber.trim().replace(/\D/g, ""),
      portfolio_link: portfolioLink.trim(),
    };
  };

  /** Dedupe by lowercased email, keeping the first occurrence. */
  const dedupeRecipients = (list) => {
    const seen = new Set();
    return list.filter((r) => {
      const key = r.email.trim().toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const runSend = async (targetRecipients) => {
    setLoading(true);
    setResults(null);
    setSendProgress({ current: 0, total: targetRecipients.length });

    const initialStatus = {};
    targetRecipients.forEach((r) => {
      initialStatus[r.email.trim()] = {
        status: "pending",
        message: "Waiting...",
      };
    });
    setRecipientStatus((prev) => ({ ...prev, ...initialStatus }));

    let base64Pdf;
    try {
      base64Pdf = await readPdfAsBase64();
    } catch (e) {
      showNotification(e.message || "Failed to read PDF file", "error");
      setLoading(false);
      return;
    }

    const collected = [];
    let successful = 0;
    let failed = 0;

    for (let i = 0; i < targetRecipients.length; i++) {
      const recipient = targetRecipients[i];
      const email = recipient.email.trim();
      setSendProgress({ current: i, total: targetRecipients.length });
      setRecipientStatus((prev) => ({
        ...prev,
        [email]: { status: "sending", message: "Sending..." },
      }));

      try {
        const response = await axios.post(`${API_BASE_URL}/send-single`, {
          recipient,
          ...commonEmailPayload(base64Pdf),
        });
        if (response.data.success) {
          successful++;
          collected.push({ email, status: "success", message: "Email sent" });
          setRecipientStatus((prev) => ({
            ...prev,
            [email]: { status: "success", message: "✅ Sent" },
          }));
        } else {
          failed++;
          const msg = response.data.error || "Failed to send";
          collected.push({ email, status: "error", message: msg });
          setRecipientStatus((prev) => ({
            ...prev,
            [email]: { status: "error", message: `❌ ${msg}` },
          }));
        }
      } catch (error) {
        failed++;
        const errorMsg = error.response?.data?.error || error.message;
        collected.push({ email, status: "error", message: errorMsg });
        setRecipientStatus((prev) => ({
          ...prev,
          [email]: { status: "error", message: `❌ ${errorMsg}` },
        }));
      }

      await new Promise((resolve) => setTimeout(resolve, 400));
    }

    setSendProgress({
      current: targetRecipients.length,
      total: targetRecipients.length,
    });

    // Merge with any prior results so a retry updates only the failed rows.
    setResults((prev) => {
      const byEmail = new Map(
        (prev?.results || []).map((r) => [r.email, r]),
      );
      collected.forEach((r) => byEmail.set(r.email, r));
      const merged = Array.from(byEmail.values());
      return {
        success: true,
        results: merged,
        summary: {
          successful: merged.filter((r) => r.status === "success").length,
          failed: merged.filter((r) => r.status === "error").length,
          total: merged.length,
        },
      };
    });

    showNotification(
      `Done. Success: ${successful}, Failed: ${failed}`,
      failed > 0 ? (successful > 0 ? "warning" : "error") : "success",
    );
    setLoading(false);
  };

  const sendEmails = async () => {
    if (!validateBeforeSend()) return;
    const target = dedupeRecipients(
      recipients.filter((r) => r.email.trim() !== ""),
    );
    await runSend(target);
  };

  const retryFailed = async () => {
    if (!results) return;
    const failedEmails = new Set(
      results.results.filter((r) => r.status === "error").map((r) => r.email),
    );
    const target = dedupeRecipients(
      recipients.filter((r) => failedEmails.has(r.email.trim())),
    );
    if (target.length === 0) {
      showNotification("No failed recipients to retry", "info");
      return;
    }
    if (!validateBeforeSend({ requireRecipients: false })) return;
    await runSend(target);
  };

  const sendTestEmail = async () => {
    const to =
      (typeof googleUser === "object" && googleUser?.email) ||
      (typeof googleUser === "object" && googleUser?.name) ||
      "";
    if (!isValidEmail(to)) {
      showNotification(
        "Sign in with Google first so we know where to send the test.",
        "warning",
      );
      return;
    }
    if (!validateBeforeSend({ requireRecipients: false })) return;

    setTestSending(true);
    try {
      const base64Pdf = await readPdfAsBase64();
      const firstWithCompany = recipients.find((r) => r.company.trim());
      const response = await axios.post(`${API_BASE_URL}/test-email`, {
        email: to,
        company: firstWithCompany?.company?.trim() || "",
        ...commonEmailPayload(base64Pdf),
      });
      if (response.data.success) {
        showNotification(`Test email sent to ${to}`, "success");
      } else {
        showNotification(response.data.error || "Test email failed", "error");
      }
    } catch (error) {
      showNotification(
        `Test failed: ${error.response?.data?.error || error.message}`,
        "error",
      );
    } finally {
      setTestSending(false);
    }
  };

  const failedCount = results?.summary?.failed || 0;
  const progressPct =
    sendProgress.total > 0
      ? Math.round((sendProgress.current / sendProgress.total) * 100)
      : 0;

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <button
            type="button"
            className="theme-toggle"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <h1>CV-Mailer</h1>
          <p>Job Application Email Automation</p>
        </header>

        <div className="card-lock-wrap">
          <div className={`card${mustSignIn ? " locked-card" : ""}`}>
            <h2>Email Configuration</h2>
            <div className="config-form">
            {googleClientId && (
              <div className="form-group">
                <label>Google account *</label>
                <div className="google-auth-row">
                  {!oauthAccessToken.trim() ? (
                    <button
                      type="button"
                      className="btn btn-add"
                      onClick={requestGoogleAccessToken}
                      disabled={!googleOAuthReady || loading}
                    >
                      Sign in with Google
                    </button>
                  ) : null}
                  {oauthAccessToken.trim() && (
                    <>
                      {googleUser === null && (
                        <span className="google-user-loading">
                          Loading account…
                        </span>
                      )}
                      {googleUser &&
                        (googleUser.email ||
                          googleUser.name ||
                          googleUser.picture) && (
                          <div className="google-user-chip">
                            {googleUser.picture ? (
                              <img
                                src={googleUser.picture}
                                alt=""
                                className="google-user-avatar"
                              />
                            ) : (
                              <div
                                className="google-user-avatar google-user-avatar--placeholder"
                                aria-hidden
                              >
                                {(googleUser.name || googleUser.email || "?")
                                  .charAt(0)
                                  .toUpperCase()}
                              </div>
                            )}
                            <div className="google-user-text">
                              <span className="google-user-name">
                                {googleUser.name ||
                                  googleUser.email ||
                                  "Google account"}
                              </span>
                              {googleUser.name && googleUser.email ? (
                                <span className="google-user-email">
                                  {googleUser.email}
                                </span>
                              ) : null}
                            </div>
                          </div>
                        )}
                      {googleUser &&
                        !googleUser.email &&
                        !googleUser.name &&
                        !googleUser.picture && (
                          <span className="google-user-loading">
                            Connected (profile unavailable)
                          </span>
                        )}
                      <button
                        type="button"
                        className="btn-google-signout"
                        onClick={clearGoogleSession}
                        disabled={loading}
                      >
                        Sign out
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}

            {config && !oauthConfigured && (
              <div className="form-group oauth-missing-notice">
                <p>
                  Google OAuth is not configured. Set{" "}
                  <code>GOOGLE_OAUTH_WEB_CLIENT_ID</code> (or{" "}
                  <code>GMAIL_OAUTH_CLIENT_ID</code> on the API) and/or server
                  Gmail OAuth env vars.
                </p>
              </div>
            )}
            <div className="form-group">
              <label htmlFor="job-title">Job Title *</label>
              <input
                id="job-title"
                type="text"
                placeholder="e.g., Senior Consultant — type your title here"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                className="input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="subject">Email Subject *</label>
              <input
                id="subject"
                type="text"
                placeholder="e.g., Job Application – Your Name"
                value={subject}
                onChange={(e) => {
                  setSubject(e.target.value);
                  setSubjectEdited(true);
                }}
                className="input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="pdf-file">CV/Resume PDF *</label>
              <label
                htmlFor="pdf-file"
                className={`dropzone${isDragging ? " dropzone--active" : ""}${
                  pdfFileName ? " dropzone--filled" : ""
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  acceptPdfFile(e.dataTransfer.files?.[0]);
                }}
              >
                <span className="dropzone-icon" aria-hidden>
                  {pdfFileName ? "📄" : "⬆️"}
                </span>
                <span className="dropzone-text">
                  {pdfFileName ? (
                    <>
                      <strong>{pdfFileName}</strong>
                      <small>Click or drop to replace</small>
                    </>
                  ) : (
                    <>
                      <strong>Drop your CV here</strong>
                      <small>
                        or click to browse · PDF up to {formatBytes(maxPdfBytes)}
                      </small>
                    </>
                  )}
                </span>
                <input
                  id="pdf-file"
                  type="file"
                  accept=".pdf"
                  onChange={(e) => {
                    acceptPdfFile(e.target.files[0]);
                    e.target.value = "";
                  }}
                  className="dropzone-input"
                />
              </label>
            </div>
            <div className="form-group">
              <label htmlFor="name">Your Name *</label>
              <input
                id="name"
                type="text"
                placeholder="e.g., Mohammad KaraBala"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="phone-number">Phone Number *</label>
              <input
                id="phone-number"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="tel"
                placeholder="e.g., 963949257963 (digits only)"
                value={phoneNumber}
                onChange={(e) =>
                  setPhoneNumber(e.target.value.replace(/\D/g, ""))
                }
                className="input"
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="portfolio-link">Portfolio link (optional)</label>
              <input
                id="portfolio-link"
                type="url"
                inputMode="url"
                placeholder="https://your-site.com"
                value={portfolioLink}
                onChange={(e) => setPortfolioLink(e.target.value)}
                className="input"
              />
            </div>
            <div className="config-actions">
              <button
                type="button"
                className="btn btn-preview"
                onClick={openEmailPreview}
                disabled={!canPreviewEmail || previewLoading || loading}
              >
                {previewLoading ? "Loading preview..." : "Preview Email"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={sendTestEmail}
                disabled={testSending || loading || !authReadyForSend}
                title="Send a copy to your own signed-in address"
              >
                {testSending ? "Sending test..." : "Send Test to Myself"}
              </button>
            </div>
          </div>
        </div>
          {mustSignIn && !showSignInModal && (
            <button
              type="button"
              className="card-lock-shield"
              onClick={() => setShowSignInModal(true)}
              aria-label="Sign in to edit your details"
            />
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Recipients</h2>
            <div className="card-header-actions">
              <button
                onClick={() => setShowImport(true)}
                className="btn btn-add"
                disabled={loading}
              >
                Import list
              </button>
              <button onClick={addRecipient} className="btn btn-add" disabled={loading}>
                + Add
              </button>
              {recipients.some((r) => r.email.trim()) && (
                <button
                  onClick={clearRecipients}
                  className="btn btn-remove"
                  disabled={loading}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div className="recipients-list">
            {recipients.map((recipient, index) => {
              const email = recipient.email.trim();
              const status = recipientStatus[email];
              const invalid = email !== "" && !isValidEmail(email);
              return (
                <div key={index} className="recipient-item">
                  <div className="recipient-row">
                    <div className="recipient-input-wrapper">
                      <input
                        type="email"
                        placeholder="Email address"
                        value={recipient.email}
                        onChange={(e) =>
                          updateRecipient(index, "email", e.target.value)
                        }
                        className={`input${invalid ? " input--invalid" : ""}`}
                        required
                        disabled={loading}
                      />
                      {status && (
                        <span
                          className={`status-indicator status-${status.status}`}
                        >
                          {status.status === "success" && "✅"}
                          {status.status === "error" && "❌"}
                          {status.status === "sending" && "⏳"}
                          {status.status === "pending" && "⏸️"}
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      placeholder="Company name (optional)"
                      value={recipient.company}
                      onChange={(e) =>
                        updateRecipient(index, "company", e.target.value)
                      }
                      className="input recipient-company"
                      disabled={loading}
                    />
                    {recipients.length > 1 && (
                      <button
                        onClick={() => removeRecipient(index)}
                        className="btn btn-remove"
                        disabled={loading}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  {invalid && (
                    <div className="status-message status-error">
                      Invalid email address
                    </div>
                  )}
                  {status && (
                    <div className={`status-message status-${status.status}`}>
                      {status.message}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {loading && sendProgress.total > 0 && (
            <div className="send-progress">
              <div className="send-progress-bar">
                <div
                  className="send-progress-fill"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <span className="send-progress-label">
                Sending {sendProgress.current} / {sendProgress.total}
              </span>
            </div>
          )}

          <button
            onClick={sendEmails}
            disabled={
              loading ||
              !authReadyForSend ||
              recipients.filter((r) => r.email.trim()).length === 0
            }
            className="btn btn-send"
          >
            {loading ? "Sending Emails..." : "Send All Emails"}
          </button>
        </div>

        {results && (
          <div className="card results-card">
            <div className="card-header">
              <h2>Results</h2>
              {failedCount > 0 && !loading && (
                <button className="btn btn-secondary" onClick={retryFailed}>
                  Retry {failedCount} failed
                </button>
              )}
            </div>
            <div className="results-summary">
              <div className="summary-item success">
                <span className="summary-label">Successful:</span>
                <span className="summary-value">
                  {results.summary.successful}
                </span>
              </div>
              <div className="summary-item failed">
                <span className="summary-label">Failed:</span>
                <span className="summary-value">{results.summary.failed}</span>
              </div>
              <div className="summary-item total">
                <span className="summary-label">Total:</span>
                <span className="summary-value">{results.summary.total}</span>
              </div>
            </div>
            <div className="results-list">
              {results.results.map((result, index) => (
                <div key={index} className={`result-item ${result.status}`}>
                  <span className="result-email">{result.email}</span>
                  <span className={`result-status ${result.status}`}>
                    {result.status === "success" ? "✅" : "❌"} {result.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <footer className="footer">
          <p>
            This site made by{" "}
            <a
              href="https://karabala-portfolio.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="footer-link"
            >
              Mohammad KaraBala
            </a>
          </p>
        </footer>
      </div>

      {mustSignIn && showSignInModal && (
        <div
          className="signin-overlay"
          onClick={(e) => {
            e.stopPropagation();
            setShowSignInModal(false);
          }}
          role="presentation"
        >
          <div
            className="signin-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="signin-title"
          >
            <div className="signin-icon" aria-hidden>
              📧
            </div>
            <h2 id="signin-title">Sign in to get started</h2>
            <p>
              Connect your Gmail account to send applications. We'll use your
              name to fill in the details — you can still edit everything
              afterwards.
            </p>
            <button
              type="button"
              className="btn btn-send signin-btn"
              onClick={requestGoogleAccessToken}
              disabled={!googleOAuthReady}
            >
              {googleOAuthReady ? "Sign in with Google" : "Loading Google…"}
            </button>
            <button
              type="button"
              className="signin-dismiss"
              onClick={() => setShowSignInModal(false)}
            >
              Maybe later
            </button>
          </div>
        </div>
      )}

      {showImport && (
        <div
          className="preview-overlay"
          onClick={() => setShowImport(false)}
          role="presentation"
        >
          <div
            className="preview-modal import-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="import-title"
          >
            <div className="preview-header">
              <div>
                <h2 id="import-title">Import recipients</h2>
                <p className="preview-subject">
                  One per line: <code>email, company</code> (company optional)
                </p>
              </div>
              <button
                type="button"
                className="btn-preview-close"
                onClick={() => setShowImport(false)}
                aria-label="Close import"
              >
                ×
              </button>
            </div>
            <div className="import-body">
              <textarea
                className="import-textarea"
                placeholder={
                  "hr@company.com, Company Inc\njobs@startup.io\nceo@example.com, Example"
                }
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
              />
              <div className="import-actions">
                <button
                  type="button"
                  className="btn btn-add"
                  onClick={() => setShowImport(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-send import-confirm"
                  onClick={importRecipients}
                >
                  Import
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showPreview && (
        <div
          className="preview-overlay"
          onClick={() => setShowPreview(false)}
          role="presentation"
        >
          <div
            className="preview-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="preview-title"
          >
            <div className="preview-header">
              <div>
                <h2 id="preview-title">Email Preview</h2>
                {subject.trim() && (
                  <p className="preview-subject">Subject: {subject.trim()}</p>
                )}
              </div>
              <button
                type="button"
                className="btn-preview-close"
                onClick={() => setShowPreview(false)}
                aria-label="Close preview"
              >
                ×
              </button>
            </div>
            <iframe
              title="Email preview"
              className="preview-iframe"
              srcDoc={previewHtml}
              sandbox=""
            />
          </div>
        </div>
      )}
      <Notification
        show={notification.show}
        message={notification.message}
        type={notification.type}
        onClose={() =>
          setNotification({ show: false, message: "", type: "info" })
        }
      />
    </div>
  );
}

export default App;
