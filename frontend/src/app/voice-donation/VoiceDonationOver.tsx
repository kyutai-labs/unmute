"use client";
import Link from "next/link";
import IntroTextOver from "./IntroTextOver.mdx";

export default function VoiceDonation() {
  return (
    <div className="w-full min-h-screen flex justify-center bg-background">
      <div className="flex flex-col justify-center max-w-xl gap-3 m-2 mb-20">
        <h1 className="text-4xl font-bold mt-4">
          Unmute Voice Donation Project
        </h1>
        <p>
          <Link href="/" className="underline">
            Back to Unmute
          </Link>
        </p>
        <div className="text-textgray">
          <IntroTextOver />
        </div>
      </div>
    </div>
  );
}
