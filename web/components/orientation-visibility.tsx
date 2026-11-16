"use client";

import { createContext, useContext, useLayoutEffect, useState } from "react";

const OrientationHiddenContext = createContext(false);
const SetOrientationHiddenContext = createContext<(hidden: boolean) => void>(() => {});

export function OrientationVisibility({ children }: { children: React.ReactNode }) {
  const [hidden, setHidden] = useState(false);

  return (
    <SetOrientationHiddenContext.Provider value={setHidden}>
      <OrientationHiddenContext.Provider value={hidden}>{children}</OrientationHiddenContext.Provider>
    </SetOrientationHiddenContext.Provider>
  );
}

export function useOrientationHidden() {
  return useContext(OrientationHiddenContext);
}

/** Hide the prep bar while this screen is in the middle of a task. */
export function useHideOrientation(hidden: boolean) {
  const setHidden = useContext(SetOrientationHiddenContext);
  useLayoutEffect(() => {
    setHidden(hidden);
    return () => setHidden(false);
  }, [hidden, setHidden]);
}
