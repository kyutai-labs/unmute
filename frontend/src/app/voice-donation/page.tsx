import { Metadata } from "next";
import VoiceDonationOver from "./VoiceDonationOver";

export const metadata: Metadata = {
  title: "Unmute Voice Donation Project",
  description: "Help us improve our voice models by donating your voice.",
};

export default function VoiceDonationOverPage() {
  // We need this wrapper to use the metadata export
  return <VoiceDonationOver />;
}
