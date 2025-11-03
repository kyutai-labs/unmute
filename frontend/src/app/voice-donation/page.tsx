import { Metadata } from "next";
import VoiceDonation from "./VoiceDonation";

export const metadata: Metadata = {
  title: "Unmute - Voice Donation",
  description: "Help us improve our voice models by donating your voice.",
};

export default function VoiceDonationPage() {
  // We need this wrapper to use the metadata export
  return <VoiceDonation />;
}
