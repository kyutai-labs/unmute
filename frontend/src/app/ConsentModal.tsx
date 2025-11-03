"use client";
import { useEffect, useState } from "react";
import SquareButton from "./SquareButton";
import { GoogleAnalytics } from "@next/third-parties/google";

// Changing this key will reset the consent state for all users
export const COOKIE_CONSENT_STORAGE_KEY = "cookieConsentV2";
export const RECORDING_CONSENT_STORAGE_KEY = "recordingConsent";

export function useConsentState(storageKey: string) {
  const [consentGiven, setConsentGiven] = useState<boolean | null>(false);
  const [consentLoaded, setConsentLoaded] = useState<boolean>(false);

  useEffect(() => {
    const consent = localStorage.getItem(storageKey);
    setConsentGiven(consent == null ? null : consent === "true");
    setConsentLoaded(true);

    // Listen for localStorage changes (in case consent is given on another tab/page)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === storageKey) {
        setConsentGiven(e.newValue === "true");
      }
    };

    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
    };
  }, [storageKey]);

  const setConsent = (to: boolean | null) => {
    if (to != null) {
      localStorage.setItem(storageKey, "" + to);
    } else {
      localStorage.removeItem(storageKey);
    }
    setConsentGiven(to);
  };

  return {
    consentGiven,
    consentLoaded, // useful to avoid hydration mismatches
    setConsent,
  };
}

export default function ConsentModal() {
  const [showDetails, setShowDetails] = useState(false);
  const {
    consentGiven: cookieConsentGiven,
    consentLoaded: cookieConsentLoaded,
    setConsent: setCookieConsent,
  } = useConsentState(COOKIE_CONSENT_STORAGE_KEY);
  const {
    consentGiven: recordingConsentGiven,
    consentLoaded: recordingConsentLoaded,
    setConsent: setRecordingConsent,
  } = useConsentState(RECORDING_CONSENT_STORAGE_KEY);
  const [recordingChecked, setRecordingChecked] = useState(true);

  useEffect(() => {
    // Only update checkbox if consent is not null (user has made a choice)
    if (recordingConsentLoaded && recordingConsentGiven !== null) {
      setRecordingChecked(recordingConsentGiven === true);
    }
  }, [recordingConsentGiven, recordingConsentLoaded]);

  if (!cookieConsentLoaded) {
    return null; // Wait until consent state is loaded
  }

  if (cookieConsentGiven === true) {
    // To debug Google Analytics, add debugMode={true} here and go to the Tag Assistant:
    // https://tagassistant.google.com/
    if (
      typeof window !== "undefined" &&
      window.location.hostname === "unmute.sh" // only load on production site
    ) {
      // If you want to use Google Analytics for your deployment, please change the GA ID and accepted hostname here.
      // Otherwise we get your traffic mixed with Unmute's traffic
      return <GoogleAnalytics gaId="G-MLN0BSWF97" />;
    } else {
      console.debug("Cookie consent given, but not loading GA since not prod");
      return null;
    }
  }

  if (cookieConsentGiven === false) {
    return null;
  }

  // consent is null, meaning it hasn't been given or declined yet
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray border-t border-green shadow-lg z-50">
      <div className="max-w-7xl mx-auto p-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex-1 text-sm text-textgray">
            <p className="text-sm text-textgray mb-2">
              Can we use cookies to improve your experience and analyze site
              usage?{" "}
              {!showDetails && (
                <button
                  onClick={() => setShowDetails(true)}
                  className="text-green underline"
                >
                  Learn more
                </button>
              )}
            </p>
            <div className="flex items-center mt-2">
              <input
                id="recording-consent-checkbox"
                type="checkbox"
                checked={recordingChecked}
                onChange={(e) => setRecordingChecked(e.target.checked)}
                className="mr-2"
              />
              <label htmlFor="recording-consent-checkbox">
                Allow us to record the transcript of the conversation (your
                voice will not be stored) to help our non-profit research
              </label>
            </div>
            {showDetails && (
              <div className="mt-3 p-3 bg-darkgray text-sm text-textgray">
                <p className="mb-2">
                  <strong>Analytics Cookies:</strong> We use Google Analytics to
                  understand how visitors interact with our website. This helps
                  us improve our content and user experience.
                </p>
                <button
                  onClick={() => setShowDetails(false)}
                  className="text-green underline"
                >
                  Learn less
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-row gap-2 w-full sm:w-auto justify-center">
            <SquareButton
              kind="primary"
              onClick={() => {
                setCookieConsent(true);
                setRecordingConsent(recordingChecked);
              }}
            >
              Accept
            </SquareButton>
            <SquareButton
              kind="secondary"
              onClick={() => {
                setCookieConsent(false);
                setRecordingConsent(false); // Cookies declined -> recording also declined
              }}
            >
              Decline
            </SquareButton>
          </div>
        </div>
      </div>
    </div>
  );
}
