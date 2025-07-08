import { useEffect, useState } from "react";

export const useBackendServerUrl = () => {
  const [backendServerUrl, setBackendServerUrl] = useState<string | null>(null);

  // Get the backend server URL. This is a bit involved to support different deployment methods.
  useEffect(() => {
    if (typeof window !== "undefined") {
      const isInDocker = ["true", "1"].includes(process.env.NEXT_PUBLIC_IN_DOCKER?.toLowerCase() || "");

      const prefix = isInDocker ? "/api" : "";

      const backendUrl = new URL("", window.location.href);
      if (!isInDocker) {
        backendUrl.port = "8000";
      }
      backendUrl.pathname = prefix;
      backendUrl.search = ""; // strip any query parameters
      setBackendServerUrl(backendUrl.toString().replace(/\/$/, "")); // remove trailing slash
    }
  }, []);

  return backendServerUrl;
};
