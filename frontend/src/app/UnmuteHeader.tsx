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
    <p className="text-xs text-right">
      Speak to an AI using our new low-latency speech-to-text and text-to-speech
      models. We{"'"}ll release these models as open source soon. Stay tuned.
    </p>
  );
};

const UnmuteHeader = () => {
  return (
    <div className="flex flex-col gap-2 py-2 md:py-8 items-end max-w-80 md:max-w-60 lg:max-w-80">
      {/* kyutaiLogo */}
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
            transcribes what you say, an LLM (we use Mistrall Small 24B) generates the
            text of the response, and we then use our text-to-speech model to
            say it out loud.
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
            intonation.
          </p>
          <p>
            Soon, we&apos;ll open-source the TTS and STT models – yes,{" "}
            <em>the same ones</em> used here! If you want to be notified when we
            do, follow us on{" "}
            <Link
              href="https://twitter.com/kyutai_labs"
              target="_blank"
              rel="noopener"
              className="underline"
            >
              Twitter
            </Link>{" "}
            or{" "}
            <Link
              href="https://www.linkedin.com/company/kyutai-labs"
              target="_blank"
              rel="noopener"
              className="underline"
            >
              LinkedIn
            </Link>
            , or{" "}
            <Link
              href="https://docs.google.com/forms/d/e/1FAIpQLSeu5GRxFOcgiAfAxFdn4LdyP6_s3jKEUNMNmaZxfH5-qdWCDQ/viewform?usp=header"
              target="_blank"
              rel="noopener"
              className="underline"
            >
              give us your email and we&apos;ll let you know
            </Link>
            .
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
