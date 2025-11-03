"use client";
import { useState } from "react";
import SlantedButton from "../SlantedButton";
import { useBackendServerUrl } from "../useBackendServerUrl";
import ErrorMessages, { ErrorItem, makeErrorItem } from "../ErrorMessages";
import VoiceRecording, { RecordedAudio } from "../VoiceRecorder";
import Link from "next/link";
import IntroText from "./IntroText.mdx";
import DonationConsent from "./DonationConsent";

type VoiceDonationVerification = {
  id: string;
  text: string;
  created_at_timestamp: number; // Seconds since epoch
};

export default function VoiceDonation() {
  const [errors, setErrors] = useState<ErrorItem[]>([]);
  const backendServerUrl = useBackendServerUrl();
  const [verification, setVerification] =
    useState<VoiceDonationVerification | null>(null);
  const [recordedAudio, setRecordedAudio] = useState<RecordedAudio | null>(
    null
  );
  const [consentGiven, setConsentGiven] = useState(false);
  const [email, setEmail] = useState("");
  const [nickname, setNickname] = useState("");

  const [uploadState, setUploadState] = useState<
    "not_started" | "uploading" | "finished"
  >("not_started");

  const [transcription, setTranscription] = useState<string>("");

  const transcribeAudio = async (audioBlobUrl: string) => {
    if (!audioBlobUrl) return;
    try {
      const blob = await fetch(audioBlobUrl).then((r) => r.blob());
      const formData = new FormData();
      formData.append("file", blob, "audio.wav");

      const response = await fetch(
        "https://unmute.sh/stt-server/api/asr-streaming?auth_id=public_token",
        {
          method: "POST",
          headers: {
            "kyutai-api-key": "public_token",
          },
          body: formData,
        }
      );
      const result = await response.json();
      const words = Array.isArray(result)
        ? result.filter((item) => item.type === "Word").map((item) => item.text)
        : [];
      setTranscription(words.join(" "));
    } catch (err) {
      setTranscription("");
      addError(
        "Failed to transcribe audio. " +
          (err instanceof Error ? err.message : "")
      );
    }
  };

  const addError = (error: string) => {
    setErrors((prev) => [...prev, makeErrorItem(error)]);
  };

  const onRecordingStarted = async () => {
    if (!backendServerUrl) return;

    try {
      // This doesn't actually exist on the backend yet
      const response = await fetch(`${backendServerUrl}/v1/voice-donation`);
      if (!response.ok) {
        throw new Error("Failed to get voice donation verification.");
      }
      const data = await response.json();
      setVerification(data);
    } catch (error) {
      // console.error("Error fetching voice donation verification:", error);
      setErrors((prev) => [
        ...prev,
        makeErrorItem(
          error instanceof Error
            ? error.message
            : "Failed to start voice donation."
        ),
      ]);
    }
  };

  const handleSubmit = async () => {
    if (!recordedAudio) {
      addError("You haven't recorded your voice yet.");
      return;
    }
    if (!verification) {
      addError("No active voice donation verification.");
      return;
    }
    if (!consentGiven) {
      addError("You must give consent to submit your voice.");
      return;
    }

    setUploadState("uploading");

    const formData = new FormData();
    formData.append("file", recordedAudio.file);

    const metadata = {
      email: email,
      nickname: nickname,
      verification_id: verification?.id || null,
      transcription_from_client: transcription,
    };
    formData.append("metadata", JSON.stringify(metadata));

    try {
      // This doesn't actually exist on the backend yet
      const response = await fetch(`${backendServerUrl}/v1/voice-donation`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        addError(error.detail);
        setUploadState("not_started");
        return;
      }

      const data = await response.json();
      console.log("Submit response:", data);
    } catch (err) {
      addError(
        err instanceof Error ? err.message : "An unknown error occurred."
      );
    }
    setUploadState("finished");
  };

  if (!backendServerUrl) {
    return (
      <div className="w-full h-screen flex justify-center items-center bg-background">
        <p>Loading...</p>
      </div>
    );
  }

  const validEmail = isValidEmail(email);

  return (
    <div className="w-full min-h-screen flex justify-center bg-background">
      <ErrorMessages errors={errors} setErrors={setErrors} />
      <div className="flex flex-col justify-center max-w-xl gap-3 m-2 mb-20">
        <h1 className="text-4xl font-bold mt-4">Voice Donation</h1>
        <p className="italic">
          <Link href="/" className="underline">
            Back to Unmute
          </Link>
        </p>
        {uploadState === "finished" && (
          <>
            <p>Thank you for donating your voice for open science &lt;3</p>
            {verification && (
              <>
                <p>
                  The identifier of your voice donation is{" "}
                  <span className="font-mono font-bold">{verification.id}</span>
                  .
                </p>
                <p>
                  You can use this identifier to find your voice later. It will
                  not be shown again, please save it now. Alternatively, you can
                  contact us at unmute@kyutai.org about your donation, see our{" "}
                  <Link
                    href="/voice-donation/privacy-policy"
                    className="underline text-green"
                  >
                    Privacy Policy
                  </Link>{" "}
                  for more details.
                </p>
                <p>
                  <Link href={"/"} className="underline">
                    Go back to Unmute
                  </Link>
                </p>
              </>
            )}
          </>
        )}
        {uploadState !== "finished" && (
          <>
            <div>
              <IntroText />
            </div>

            {!recordedAudio && (
              <p>
                You&apos;ll have the chance to listen to your recording before
                submitting it.
              </p>
            )}
            <VoiceRecording
              setRecordedAudio={(audio) => {
                setRecordedAudio(audio);
                if (audio?.blobUrl) {
                  transcribeAudio(audio.blobUrl);
                }
              }}
              setError={(error: string | null) => {
                if (!error) return;
                addError(error);
              }}
              recordingDurationSec={30}
              onRecordingStarted={onRecordingStarted}
              showProgress={false}
            />
            {verification && (
              <div>
                <p>Start by saying:</p>
                <p className="italic">{verification.text}</p>
              </div>
            )}
            {/* {!verification && <div className="mt-20"></div>} */}
            {recordedAudio && (
              <div className="flex flex-col gap-2">
                <audio
                  controls
                  src={recordedAudio.blobUrl}
                  className="w-full mt-2"
                />
                {transcription && (
                  <div className="bg-gray text-white my-2 px-2 py-4 rounded">
                    <strong>Transcription:</strong>
                    <p className="mt-1">{transcription}</p>
                  </div>
                )}
                <label className="flex flex-col gap-1">
                  Email to contact you if needed, or if you choose to withdraw
                  (not published):
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="border px-2 py-1 bg-gray text-white"
                  />
                  {!validEmail && email && (
                    <span className="text-red text-sm">
                      Please enter a valid email address.
                    </span>
                  )}
                </label>
                <label className="flex flex-col gap-1">
                  (Optional) Preferred nickname for the voice if published:
                  <input
                    type="text"
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    className="border px-2 py-1 bg-gray text-white"
                  />
                </label>
                <DonationConsent setConsentGiven={setConsentGiven} />
                <SlantedButton
                  kind={
                    consentGiven && validEmail && uploadState === "not_started"
                      ? "primary"
                      : "disabled"
                  }
                  onClick={handleSubmit}
                >
                  {uploadState === "uploading" ? "Uploading..." : "Submit"}
                </SlantedButton>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function isValidEmail(email: string): boolean {
  // Basic email regex for validation
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
