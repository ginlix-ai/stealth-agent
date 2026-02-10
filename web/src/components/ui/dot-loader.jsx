import { useCallback, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

const LOADER_FRAMES = [
  [14, 7, 0, 8, 6, 13, 20],
  [14, 7, 13, 20, 16, 27, 21],
  [14, 20, 27, 21, 34, 24, 28],
  [27, 21, 34, 28, 41, 32, 35],
  [34, 28, 41, 35, 48, 40, 42],
  [34, 28, 41, 35, 48, 42, 46],
  [34, 28, 41, 35, 48, 42, 38],
  [34, 28, 41, 35, 48, 30, 21],
  [34, 28, 41, 48, 21, 22, 14],
  [34, 28, 41, 21, 14, 16, 27],
  [34, 28, 21, 14, 10, 20, 27],
  [28, 21, 14, 4, 13, 20, 27],
  [28, 21, 14, 12, 6, 13, 20],
  [28, 21, 14, 6, 13, 20, 11],
  [28, 21, 14, 6, 13, 20, 10],
  [14, 6, 13, 20, 9, 7, 21],
];

export function DotLoader({
  frames = LOADER_FRAMES,
  isPlaying = true,
  duration = 100,
  dotClassName,
  className,
  repeatCount = -1,
  onComplete,
  ...props
}) {
  const gridRef = useRef(null);
  const currentIndex = useRef(0);
  const repeats = useRef(0);
  const interval = useRef(null);

  const applyFrameToDots = useCallback(
    (dots, frameIndex) => {
      const frame = frames[frameIndex];
      if (!frame) return;
      dots.forEach((dot, index) => {
        dot.classList.toggle("active", frame.includes(index));
      });
    },
    [frames],
  );

  useEffect(() => {
    currentIndex.current = 0;
    repeats.current = 0;
  }, [frames]);

  useEffect(() => {
    if (isPlaying) {
      if (currentIndex.current >= frames.length) {
        currentIndex.current = 0;
      }
      const dotElements = gridRef.current?.children;
      if (!dotElements) return;
      const dots = Array.from(dotElements);
      interval.current = setInterval(() => {
        applyFrameToDots(dots, currentIndex.current);
        if (currentIndex.current + 1 >= frames.length) {
          if (repeatCount !== -1 && repeats.current + 1 >= repeatCount) {
            clearInterval(interval.current);
            onComplete?.();
          }
          repeats.current++;
        }
        currentIndex.current = (currentIndex.current + 1) % frames.length;
      }, duration);
    } else {
      if (interval.current) clearInterval(interval.current);
    }

    return () => {
      if (interval.current) clearInterval(interval.current);
    };
  }, [frames, isPlaying, applyFrameToDots, duration, repeatCount, onComplete]);

  return (
    <div {...props} ref={gridRef} className={cn("grid w-fit grid-cols-7 gap-0.5", className)}>
      {Array.from({ length: 49 }).map((_, i) => (
        <div key={i} className={cn("h-1.5 w-1.5 rounded-sm", dotClassName)} />
      ))}
    </div>
  );
}

export default DotLoader;
