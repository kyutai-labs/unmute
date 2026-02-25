import { Frank_Ruhl_Libre } from "next/font/google";
import Modal from "./Modal";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import kyutaiLogo from "../assets/kyutai-logo-cropped.svg";

const frankRuhlLibre = Frank_Ruhl_Libre({
  weight: "400",
  subsets: ["latin"],
});

const ShortExplanation = () => {
  return (
    <>
      <p className="text-xs text-right">
        Speak to an AI using our low-latency open-source{" "}
        <Link
          href="https://kyutai.org/stt"
          className="underline text-green"
          target="_blank"
          rel="noopener"
        >
          speech-to-text
        </Link>{" "}
        and{" "}
        <Link
          href="https://kyutai.org/tts"
          className="underline text-green"
          target="_blank"
          rel="noopener"
        >
          text-to-speech
        </Link>
        .
      </p>
      <p className="text-xs text-right">
        Also check out{" "}
        <Link
          href="https://kyutai.org/pocket-tts?ref=unmute"
          className="underline text-green"
          target="_blank"
          rel="noopener"
        >
          Pocket TTS
        </Link>
        , our new tiny TTS model with voice cloning!
      </p>
    </>
  );
};

const UnmuteHeader = () => {
  return (
    <div className="flex flex-col gap-2 py-2 md:py-8 items-end max-w-80 md:max-w-60 xl:max-w-80">
      <h1 className={`text-3xl ${frankRuhlLibre.className}`}>Unmute.sh</h1>
      <div className="flex items-center gap-2 -mt-1 text-xs">
        by
        <Link href="https://kyutai.org" target="_blank" rel="noopener">
          <img src={kyutaiLogo.src} alt="Kyutai logo" className="w-20" />
        </Link>
      </div>
      <ShortExplanation />
      <Modal
        trigger={
          <span className="flex items-center gap-1 text-lightgray">
            More info <ArrowUpRight size={24} />
          </span>
        }
        forceFullscreen={true}
      >
        <div className="flex flex-col gap-3">
          <p>
            This is a cascaded system made by Kyutai: our speech-to-text
            transcribes what you say, an LLM (we use Gemma 3 12B)
            generates the text of the response, and we then use our
            text-to-speech model to say it out loud.
          </p>
          <p>
            All of the components are open-source:{" "}
            <Link
              href="https://kyutai.org/stt"
              target="_blank"
              rel="noopener"
              className="underline text-green"
            >
              Kyutai STT
            </Link>
            ,{" "}
            <Link
              href="https://kyutai.org/tts"
              target="_blank"
              rel="noopener"
              className="underline text-green"
            >
              Kyutai TTS 1.6B
            </Link>
            , and{" "}
            <Link
              href="https://kyutai.org/unmute"
              target="_blank"
              rel="noopener"
              className="underline text-green"
            >
              Unmute
            </Link>{" "}
            itself.
          </p>
          <p>
            Although cascaded systems lose valuable information like emotion,
            irony, etc., they provide unmatched modularity: since the three
            parts are separate, you can <em>Unmute</em> any LLM you want without
            any finetuning or adaptation! In this demo, you can get a feel for
            this versatility by tuning the system prompt of the LLM to handcraft
            the personality of your digital interlocutor, and independently
            changing the voice of the TTS.
          </p>
          <p>
            Both the speech-to-text and text-to-speech models are optimized for
            low latency. The STT model is streaming and integrates semantic
            voice activity detection instead of relying on an external model.
            The TTS is streaming both in audio and in text, meaning it can start
            speaking before the entire LLM response is generated. You can use a
            10-second voice sample to determine the TTS{"'"}s voice and
            intonation. Check out the{" "}
            <Link
              href="https://arxiv.org/pdf/2509.08753"
              target="_blank"
              rel="noopener"
              className="underline text-green"
            >
              pre-print
            </Link>{" "}
            for details.
          </p>
          <p>
            To stay up to date on our research, follow us on{" "}
            <Link
              href="https://twitter.com/kyutai_labs"
              target="_blank"
              rel="noopener"
              className="underline text-green"
            >
              X/Twitter
            </Link>{" "}
            or{" "}
            <Link
              href="https://www.linkedin.com/company/kyutai-labs"
              target="_blank"
              rel="noopener"
              className="underline text-green"
            >
              LinkedIn
            </Link>.
          </p>
          <p>
            For questions or feedback:{" "}
            <Link
              href="mailto:unmute@kyutai.org"
              target="_blank"
              rel="noopener"
              className="underline"
            >
              unmute@kyutai.org
            </Link>
          </p>
        </div>
      </Modal>
    </div>
  );
};

export default UnmuteHeader;
