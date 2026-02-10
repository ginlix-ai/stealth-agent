import { cn } from "@/lib/utils";

const containerSizes = {
  sm: "w-4 h-4",
  md: "w-6 h-6",
  lg: "w-8 h-8",
};

export default function MorphLoading({ size = "md", className }) {
  return (
    <div className={cn("relative", containerSizes[size], className)}>
      <div className="absolute inset-0 flex items-center justify-center">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="absolute rounded-none bg-current"
            style={{
              width: '15%',
              height: '15%',
              animation: `morph-${i} 2s infinite ease-in-out`,
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
