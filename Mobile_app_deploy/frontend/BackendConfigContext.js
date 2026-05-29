import React from "react";

export const BackendConfigContext = React.createContext({
    backendIp: "",
    setBackendIp: () => {},
});

export const buildBaseUrl = (backendIp) => {
    let trimmed = (backendIp || "").trim();
    if (!trimmed) {
        return "";
    }
    if (!/^https?:\/\//i.test(trimmed)) {
        trimmed = `http://${trimmed}`;
    }
    return trimmed.replace(/\/+$/, "");
};
