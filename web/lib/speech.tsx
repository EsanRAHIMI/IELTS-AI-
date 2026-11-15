"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "ielts_speak";

const VOICE_RANK = [
  /google us english$/i,
  /google us english/i,
  /samantha/i,
  /alex/i,
  /ava \(enhanced\)/i,
  /aria/i,
  /jenny/i,
  /guy/i,
  /zira/i,
  /david/i,
];

export function pickAmericanVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const clear = voices.filter((voice) => !/compact|espeak|whisper/i.test(voice.name));
  const american = clear.filter((voice) => /^en[-_]US$/i.test(voice.lang));
  const pool = american.length ? american : clear.filter((voice) => voice.lang.toLowerCase().startsWith("en"));
  for (const pattern of VOICE_RANK) {
    const match = pool.find((voice) => pattern.test(voice.name));
    if (match) return match;
  }
  return pool[0] || null;
}

function readStored(): boolean {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "0") return false;
    if (stored === "1") return true;
  } catch {
    /* private mode */
  }
  return true;
}

type SpeechControls = {
  enabled: boolean;
  ready: boolean;
  toggle: () => void;
  speak: (text: string) => void;
  stop: () => void;
};

const SpeechContext = createContext<SpeechControls>({
  enabled: true,
  ready: false,
  toggle: () => {},
  speak: () => {},
  stop: () => {},
});

function voicesReady(synth: SpeechSynthesis): Promise<SpeechSynthesisVoice[]> {
  const current = synth.getVoices();
  if (current.length) return Promise.resolve(current);
  return new Promise((resolve) => {
    const finish = () => {
      const list = synth.getVoices();
      if (!list.length) return;
      synth.removeEventListener("voiceschanged", finish);
      resolve(list);
    };
    synth.addEventListener("voiceschanged", finish);
    window.setTimeout(() => {
      synth.removeEventListener("voiceschanged", finish);
      resolve(synth.getVoices());
    }, 700);
  });
}

export function SpeechProvider({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(true);
  const [ready, setReady] = useState(false);
  const enabledRef = useRef(false);
  const ticket = useRef(0);

  useEffect(() => {
    const on = readStored();
    enabledRef.current = on;
    setEnabled(on);
    setReady(true);
  }, []);

  const stop = useCallback(() => {
    ticket.current += 1;
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback((text: string) => {
    const line = text.replace(/\s+/g, " ").trim();
    if (!line || !enabledRef.current) return;
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const synth = window.speechSynthesis;
    const mine = ++ticket.current;
    synth.cancel();
    window.setTimeout(() => {
      if (mine !== ticket.current || !enabledRef.current) return;
      void voicesReady(synth).then((voices) => {
        if (mine !== ticket.current || !enabledRef.current) return;
        const utterance = new SpeechSynthesisUtterance(line);
        utterance.lang = "en-US";
        utterance.rate = 0.95;
        utterance.pitch = 1;
        const voice = pickAmericanVoice(voices);
        if (voice) utterance.voice = voice;
        synth.resume();
        synth.speak(utterance);
      });
    }, 40);
  }, []);

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      enabledRef.current = next;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      if (!next) stop();
      return next;
    });
  }, [stop]);

  return (
    <SpeechContext.Provider value={{ enabled, ready, toggle, speak, stop }}>
      {children}
    </SpeechContext.Provider>
  );
}

export function useSpeech() {
  return useContext(SpeechContext);
}
