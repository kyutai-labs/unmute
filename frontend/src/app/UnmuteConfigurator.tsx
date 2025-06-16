import { useEffect, useState } from "react";
import VoiceAttribution from "./VoiceAttribution";
import SquareButton from "./SquareButton";
import Modal from "./Modal";
import { ArrowUpRight } from "lucide-react";
import VoiceUpload from "./VoiceUpload";
// import VoiceUpload from "./VoiceUpload";

export type LanguageCode = "en" | "fr" | "en/fr" | "fr/en";

export type ConstantInstructions = {
  type: "constant";
  text: string;
  language?: LanguageCode;
};

export type Instructions =
  | ConstantInstructions
  | { type: "smalltalk"; language?: LanguageCode }
  | { type: "guess_animal"; language?: LanguageCode }
  | { type: "quiz_show"; language?: LanguageCode };

export type UnmuteConfig = {
  instructions: Instructions;
  voice: string;
  // The backend doesn't care about this, we use it for analytics
  voiceName: string;
  // The backend doesn't care about this, we use it for analytics
  isCustomInstructions: boolean;
};

// Will be overridden immediately by the voices fetched from the backend
export const DEFAULT_UNMUTE_CONFIG: UnmuteConfig = {
  instructions: {
    type: "smalltalk",
    language: "en/fr",
  },
  voice: "barack_demo.wav",
  voiceName: "Missing voice",
  isCustomInstructions: false,
};

export type FreesoundVoiceSource = {
  source_type: "freesound";
  url: string;
  start_time: number;
  sound_instance: {
    id: number;
    name: string;
    username: string;
    license: string;
  };
  path_on_server: string;
};

export type FileVoiceSource = {
  source_type: "file";
  path_on_server: string;
  description?: string;
  description_link?: string;
};

export type VoiceSample = {
  name: string | null;
  comment: string;
  good: boolean;
  instructions: Instructions | null;
  source: FreesoundVoiceSource | FileVoiceSource;
};

const instructionsToPlaceholder = (instructions: Instructions) => {
  if (instructions.type === "constant") {
    return instructions.text;
  } else {
    return (
      {
        smalltalk:
          "Make pleasant conversation. (For this character, the instructions contain dynamically generated parts.)",
        guess_animal:
          "Make the user guess the animal. (For this character, the instructions contain dynamically generated parts.)",
        quiz_show:
          "You're a quiz show host that hates his job. (For this character, the instructions contain dynamically generated parts.)",
        news: "Talk about the latest tech news. (For this character, we fetch the news from the internet dynamically.)",
        unmute_explanation:
          "Explain how Unmute works. (For this character, the instructions are long so we don't show them here in full.)",
      }[instructions.type] || ""
    );
  }
};

const fetchVoices = async (
  backendServerUrl: string
): Promise<VoiceSample[]> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(`${backendServerUrl}/v1/voices`, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      console.error("Failed to fetch voices:", response.statusText);
      return [];
    }

    const voices = await response.json();
    return voices;
  } catch (error) {
    console.error("Error fetching voices:", error);
    return [];
  }
};

const getVoiceName = (voice: VoiceSample) => {
  return (
    voice.name ||
    (voice.source.source_type === "freesound"
      ? voice.source.sound_instance.username
      : voice.source.path_on_server.slice(0, 10))
  );
};

const UnmuteConfigurator = ({
  config,
  backendServerUrl,
  setConfig,
  voiceCloningUp,
}: {
  config: UnmuteConfig;
  backendServerUrl: string;
  setConfig: (config: UnmuteConfig) => void;
  voiceCloningUp: boolean;
}) => {
  const [voices, setVoices] = useState<VoiceSample[] | null>(null);
  const [customVoiceName, setCustomVoiceName] = useState<string | null>(null);
  const [customInstructions, setCustomInstructions] =
    useState<Instructions | null>(null);

  useEffect(() => {
    const fetchVoicesData = async () => {
      if (backendServerUrl && voices === null) {
        const voicesData = await fetchVoices(backendServerUrl);
        setVoices(voicesData);

        // It could be confusing to start with a non-English voice
        const englishVoices = voicesData.filter(
          (voice) => (voice.instructions?.language || "en") === "en"
        );
        const randomVoice =
          englishVoices[Math.floor(Math.random() * englishVoices.length)];

        setConfig({
          ...config,
          voice: randomVoice.source.path_on_server,
          voiceName: getVoiceName(randomVoice),
          instructions:
            randomVoice.instructions || DEFAULT_UNMUTE_CONFIG.instructions,
        });
      }
    };

    fetchVoicesData();
  }, [backendServerUrl, config, setConfig, voices]);

  if (!voices) {
    return (
      <div className="w-full">
        <p className="text-lightgray">Loading voices...</p>
      </div>
    );
  }

  const onCustomVoiceUpload = (name: string) => {
    setCustomVoiceName(name);
    setConfig({
      voice: name,
      instructions: customInstructions || DEFAULT_UNMUTE_CONFIG.instructions,
      isCustomInstructions: !!customInstructions,
      voiceName: "custom",
    });
  };

  const activeVoice = voices.find(
    (voice) => voice.source.path_on_server === config.voice
  );
  const defaultInstructions =
    activeVoice?.instructions || DEFAULT_UNMUTE_CONFIG.instructions;

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const updatedInstructions: Instructions | null = e.target.value
      ? { type: "constant", text: e.target.value, language: "en/fr" }
      : null;
    setCustomInstructions(updatedInstructions);
    console.debug("Updated instructions:", updatedInstructions);
    setConfig({
      ...config,
      instructions: updatedInstructions || defaultInstructions,
      isCustomInstructions: !!updatedInstructions,
    });
  };

  const additionalInstructionsHeader = (
    <div className="w-full flex flex-row items-center gap-2">
      <Modal
        trigger={
          <h2 className="pb-1 flex items-center gap-1 text-lightgray">
            Instructions <ArrowUpRight size={24} />
          </h2>
        }
      >
        <div className="flex flex-col gap-3">
          <p>
            Instructions that affect the text responses generated by the LLM.
            Note that{" "}
            <em className="italic">
              the text-to-speech does not have access to these,{" "}
            </em>
            meaning voice instructions like {'"speak slowly"'} will not work.
          </p>
          {config.instructions.type !== "constant" && (
            <p>
              *In this case, some instructions are generated dynamically and
              change each time.
            </p>
          )}
        </div>
      </Modal>
      <div className="h-0.5 bg-gray grow hidden md:visible"></div>
    </div>
  );

  return (
    <div className="w-full flex flex-col items-center">
      {/* Separate header div, because it has a different background */}
      <div className="w-full max-w-6xl grid grid-flow-row grid-cols-1 md:grid-cols-2 gap-3 px-3">
        <div className="w-full flex flex-row items-center gap-2">
          <Modal
            trigger={
              <h2 className="pb-1 cursor-pointer flex items-center gap-1 text-lightgray">
                Character <ArrowUpRight size={24} />
              </h2>
            }
          >
            <p>
              The voice of the text-to-speech is based on a 10-second sample.
            </p>
            {activeVoice && <VoiceAttribution voice={activeVoice} />}
          </Modal>
          <div className="h-0.5 bg-gray grow hidden md:visible"></div>
        </div>
        <div className="hidden md:inline-block">
          {additionalInstructionsHeader}
        </div>
      </div>
      {/* Gray background div, full width */}
      <div className="w-full md:bg-gray flex flex-col items-center">
        <div className="w-full max-w-6xl grid grid-flow-row grid-cols-1 md:grid-cols-2 gap-3 p-3">
          <div>
            <div className="grid grid-flow-row grid-cols-2 md:grid-cols-3 gap-3">
              {voices &&
                voices.map((voice) => (
                  <SquareButton
                    key={voice.source.path_on_server}
                    onClick={() => {
                      setConfig({
                        voice: voice.source.path_on_server,
                        voiceName: voice.name || "Unnamed",
                        instructions:
                          customInstructions ||
                          voice.instructions ||
                          DEFAULT_UNMUTE_CONFIG.instructions,
                        isCustomInstructions: !!customInstructions,
                      });
                    }}
                    kind={
                      voice.source.path_on_server === config.voice
                        ? "primary"
                        : "secondary"
                    }
                    extraClasses="bg-gray md:bg-black"
                  >
                    {"/ " + getVoiceName(voice) + " /"}
                  </SquareButton>
                ))}
              {voiceCloningUp && (
                <VoiceUpload
                  backendServerUrl={backendServerUrl}
                  onCustomVoiceUpload={onCustomVoiceUpload}
                  isSelected={customVoiceName === config.voice}
                />
              )}
            </div>
          </div>
          <div className="inline-block md:hidden">
            {additionalInstructionsHeader}
          </div>
          <textarea
            placeholder={instructionsToPlaceholder(defaultInstructions)}
            onChange={handleChange}
            className="bg-gray md:bg-black text-white text-sm w-full p-2 resize-none h-33"
            style={{
              filter: "drop-shadow(-0.1rem -0.1rem 0.1rem var(--darkgray))",
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default UnmuteConfigurator;
