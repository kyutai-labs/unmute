import { useState } from "react";
import { Upload } from "lucide-react";
import VoiceButton from "./SquareButton";
import Modal from "./Modal";
import SlantedButton from "@/app/SlantedButton";
import Link from "next/link";
import VoiceRecorder, { MIC_RECORDING_FILENAME } from "./VoiceRecorder";
import TrimmedAudioPreview from "./TrimmedAudioPreview";

// Also checked on the backend, see constant of the same name
const MAX_VOICE_FILE_SIZE_MB = 4;

const VoiceUpload = ({
  backendServerUrl,
  onCustomVoiceUpload,
  isSelected,
}: {
  backendServerUrl: string;
  onCustomVoiceUpload: (name: string) => void;
  isSelected: boolean;
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Increment this to force the modal to close
  const [closeSignal, setCloseSignal] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.size > MAX_VOICE_FILE_SIZE_MB * 1024 * 1024) {
        setError(`File size must be less than ${MAX_VOICE_FILE_SIZE_MB} MB.`);
        setFile(null);
      } else {
        setError(null);
        setFile(selectedFile);
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }

    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${backendServerUrl}/v1/voices`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(
          `Failed to upload file (${response.status} ${response.statusText}).`,
        );
      }

      const data = await response.json();
      if (data.name) {
        onCustomVoiceUpload(data.name);
      } else {
        throw new Error("Invalid response from server.");
      }
      setCloseSignal((prev) => prev + 1);

      // Clear the file so that the next time we open the modal, we don't see the old file.
      // You can still keep using the old file by closing the modal without uploading anything.
      // The delay is prevent a flash before the modal closes.
      setTimeout(() => {
        setFile(null);
      }, 1000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unknown error occurred.",
      );
    }
    setIsUploading(false);
  };

  return (
    <Modal
      trigger={
        <VoiceButton
          kind={isSelected ? "primary" : "secondary"}
          extraClasses="w-full bg-gray md:bg-black"
        >
          Upload <Upload size={16} className="inline" />
        </VoiceButton>
      }
      forceFullscreen={true}
      closeSignal={closeSignal}
    >
      <div className="flex flex-col gap-3">
        <p>
          Upload a voice sample to use as Unmute{"'"}s voice. The first 10
          seconds of the audio are used. The audio file may be at most{" "}
          {MAX_VOICE_FILE_SIZE_MB}&nbsp;MB. The TTS mimics the audio quality as
          well, so use a high-quality recording. Post-processing your recording
          using a tool like{" "}
          <Link
            href="https://podcast.adobe.com/en/enhance"
            className="underline text-green"
            target="_blank"
            rel="noopener"
          >
            Adobe Podcast AI
          </Link>{" "}
          is usually enough.
        </p>
        <p>
          We keep the embedding of the voice on our server for 1 hour. We do not
          store the uploaded audio itself.
        </p>
        <p>
          We provide this voice cloning ability for experimental and educational
          purposes only. Use responsibly.
        </p>
        <p>
          More voices for Kyutai TTS 1.6B are available in our{" "}
          <Link
            href="https://huggingface.co/kyutai/tts-voices"
            className="underline text-green"
          >
            voice repository
          </Link>
          .
        </p>
        <p className="mb-2">
          Also check out{" "}
          <Link
            href="https://kyutai.org/pocket-tts?ref=unmute"
            className="underline text-green"
          >
            Pocket TTS
          </Link>
          , our new 100M-parameter model with voice cloning from any file.
        </p>
        {!file && (
          <div className="flex flex-row gap-2 justify-center">
            <div className="relative">
              <input
                type="file"
                accept="audio/*"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-50"
              />
              <SlantedButton kind="primary">Choose Audio File</SlantedButton>
            </div>
            <VoiceRecorder
              setRecordedAudio={(recordedAudio) => {
                setFile(recordedAudio.file);
              }}
              setError={setError}
              recordingDurationSec={10}
            />
          </div>
        )}
        {file && (
          <>
            <TrimmedAudioPreview file={file} />
            <div className="flex flex-row justify-center">
              <SlantedButton kind="secondary" onClick={() => setFile(null)}>
                Remove
              </SlantedButton>
              <SlantedButton
                onClick={handleUpload}
                kind={file != null && !isUploading ? "primary" : "disabled"}
                extraClasses="grow"
              >
                {isUploading
                  ? "Uploading..."
                  : file && file.name === MIC_RECORDING_FILENAME
                    ? "Select recording"
                    : "Select"}
              </SlantedButton>
            </div>
          </>
        )}
        {error && <p className="text-red text-sm mt-2">Error: {error}</p>}
      </div>
    </Modal>
  );
};

export default VoiceUpload;
