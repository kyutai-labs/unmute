"use client";
import { useEffect } from "react";

interface RedirectProps {
  link: string;
  name: string;
}

export default function Redirect({ link, name }: RedirectProps) {
  useEffect(() => {
    window.location.href = link;
  }, [link]);
  return (
    <div>
      <p>Redirecting to {name}...</p>
      <a href={link}>Click here if not redirected.</a>
    </div>
  );
}
