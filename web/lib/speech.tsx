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

type SpeakOptions = { force?: boolean };

type SpeechControls = {
  enabled: boolean;
  ready: boolean;
  toggle: () => void;
  speak: (text: string, opts?: SpeakOptions) => void;
  stop: () => void;
};

const SpeechContext = createContext<SpeechControls>({
  enabled: true,
  ready: false,
  toggle: () => {},
  speak: () => {},
  stop: () => {},
});

function iosSpeech(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

function activationActive(): boolean {
  const nav = navigator as Navigator & { userActivation?: { isActive?: boolean } };
  return !!nav.userActivation?.isActive;
}

function cleanLine(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

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
  const unlockedRef = useRef(false);
  const primedRef = useRef(false);
  const pendingRef = useRef<{ text: string; force: boolean } | null>(null);
  const speakRef = useRef<(text: string, opts?: SpeakOptions) => void>(() => {});

  useEffect(() => {
    const on = readStored();
    enabledRef.current = on;
    setEnabled(on);
    setReady(true);
  }, []);

  const stop = useCallback(() => {
    ticket.current += 1;
    pendingRef.current = null;
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback((text: string, opts?: SpeakOptions) => {
    const line = cleanLine(text);
    const force = !!opts?.force;
    if (!line) return;
    if (!force && !enabledRef.current) return;
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const synth = window.speechSynthesis;
    const ios = iosSpeech();

    // A speak() call before the first tap on iPhone Chrome is ignored and
    // leaves the engine stuck until the speaker control is toggled.
    if (ios && !force && !unlockedRef.current && !activationActive()) {
      pendingRef.current = { text: line, force: false };
      return;
    }
    if (ios && (force || activationActive())) unlockedRef.current = true;

    const mine = ++ticket.current;
    const start = (voices?: SpeechSynthesisVoice[]) => {
      if (mine !== ticket.current) return;
      if (!force && !enabledRef.current) return;
      const utterance = new SpeechSynthesisUtterance(line);
      utterance.lang = "en-US";
      utterance.rate = 0.95;
      utterance.pitch = 1;
      const voice = pickAmericanVoice(voices || synth.getVoices());
      if (voice) {
        try { utterance.voice = voice; } catch { /* use the lang default */ }
      }
      const resume = () => {
        if (mine !== ticket.current) return;
        try { synth.resume(); } catch { /* already idle */ }
      };
      utterance.onstart = () => resume();
      resume();
      synth.speak(utterance);
      if (!ios) return;
      const kick = window.setInterval(() => {
        if (mine !== ticket.current) {
          window.clearInterval(kick);
          return;
        }
        resume();
      }, 120);
      window.setTimeout(() => window.clearInterval(kick), 1600);
    };

    const busy = synth.speaking || synth.pending;
    if (ios) {
      if (busy) {
        synth.cancel();
        window.setTimeout(() => start(), 50);
      } else {
        start();
      }
      return;
    }

    synth.cancel();
    window.setTimeout(() => {
      if (mine !== ticket.current || (!force && !enabledRef.current)) return;
      void voicesReady(synth).then((voices) => start(voices));
    }, 40);
  }, []);

  speakRef.current = speak;

  useEffect(() => {
    if (!iosSpeech()) return;
    const onGesture = (event: Event) => {
      const target = event.target;
      if (target instanceof Element && target.closest("[data-pronounce]")) return;
      const pending = pendingRef.current;
      const wasUnlocked = unlockedRef.current;
      unlockedRef.current = true;
      if (pending) {
        pendingRef.current = null;
        speakRef.current(pending.text, { force: pending.force });
        return;
      }
      if (wasUnlocked || primedRef.current || !window.speechSynthesis) return;
      primedRef.current = true;
      try {
        const synth = window.speechSynthesis;
        synth.resume();
        const primer = new SpeechSynthesisUtterance("a");
        primer.volume = 0;
        primer.lang = "en-US";
        primer.rate = 2;
        synth.speak(primer);
      } catch {
        /* the next tap speaks the real word */
      }
    };
    window.addEventListener("pointerdown", onGesture, true);
    window.addEventListener("touchend", onGesture, true);
    return () => {
      window.removeEventListener("pointerdown", onGesture, true);
      window.removeEventListener("touchend", onGesture, true);
    };
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
