import React from "react";
import "./Notification.css";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "./Icons";

function Notification({ message, type, onClose, show }) {
  if (!show) return null;

  const typeClass = type || "info";
  const IconComp =
    type === "success"
      ? CheckCircle
      : type === "error"
        ? XCircle
        : type === "warning"
          ? AlertTriangle
          : Info;

  return (
    <div
      className={`notification notification-${typeClass} ${show ? "show" : ""}`}
    >
      <div className="notification-content">
        <span className="notification-icon">
          <IconComp size={20} />
        </span>
        <span className="notification-message">{message}</span>
        <button
          className="notification-close"
          onClick={onClose}
          aria-label="Dismiss"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
}

export default Notification;
