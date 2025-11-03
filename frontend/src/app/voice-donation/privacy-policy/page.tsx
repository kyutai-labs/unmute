// A redirection page, set up so that we can change the URL it points to later if needed.
import Redirect from "../Redirect";

export const metadata = {
  title: "Voice Donation Privacy Policy",
  description: "Privacy Policy for the Unmute Voice Donation project.",
};

const LINK =
  "https://kyutai.org/next/legal/Privacy%20Policy%20-%20Unmute%20Voice%20Donation%20Project%20v1.pdf";

export default function PrivacyPolicyRedirect() {
  return <Redirect link={LINK} name="Voice Donation Privacy Policy" />;
}
