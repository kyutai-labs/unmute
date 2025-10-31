import { useEffect, useState } from "react";

export const useBackendServerUrl = () => {
  const [backendServerUrl, setBackendServerUrl] = useState<string | null>(null);

  // Get the backend server URL. This is a bit involved to support different deployment methods.
  useEffect(() => {
    const logResolvedUrl = (source: string, url: string) => {
      console.info(`[useBackendServerUrl] Using ${source} backend URL: ${url}`);
    };

    if (typeof window !== "undefined") {
      const isInDocker = ["true", "1"].includes(process.env.NEXT_PUBLIC_IN_DOCKER?.toLowerCase() || "");

      const prefix = isInDocker ? "/api" : "";

      const rawEnvUrl = process.env.NEXT_PUBLIC_BACKEND_SERVER_URL?.trim();
      if (rawEnvUrl) {
        try {
          const backendUrl = rawEnvUrl.includes("://")
            ? new URL(rawEnvUrl)
            : new URL(`${window.location.protocol}//${rawEnvUrl}`);

          const hasCustomPath =
            backendUrl.pathname !== "" &&
            backendUrl.pathname !== "/" &&
            backendUrl.pathname !== prefix;
          if (!hasCustomPath && prefix) {
            backendUrl.pathname = prefix;
          }
          backendUrl.search = "";

          const resolvedUrl = backendUrl.toString().replace(/\/$/, "");
          setBackendServerUrl(resolvedUrl);
          logResolvedUrl("env", resolvedUrl);
          return;
        } catch (error) {
          console.error(
            "Invalid NEXT_PUBLIC_BACKEND_SERVER_URL. Falling back to default.",
            rawEnvUrl,
            error
          );
        }
      }

      const backendUrl = new URL("", window.location.href);
      if (!isInDocker && !rawEnvUrl) {
        backendUrl.port = "8000";
      }
      backendUrl.pathname = prefix;
      backendUrl.search = ""; // strip any query parameters
      const resolvedUrl = backendUrl.toString().replace(/\/$/, ""); // remove trailing slash
      setBackendServerUrl(resolvedUrl);
      logResolvedUrl("default", resolvedUrl);
    }
  }, []);

  return backendServerUrl;
};
