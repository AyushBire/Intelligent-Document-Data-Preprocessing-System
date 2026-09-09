interface Props {
  progress: number;
  stage: string;
  status: string;
}

const stageLabels: Record<string, string> = {
  preprocessing: "Preprocessing image...",
  ocr: "Running OCR...",
  llm: "Analyzing with AI...",
  saving: "Saving to database...",
  done: "Complete!",
};

export default function ProgressBar({ progress, stage, status }: Props) {
  const isError = status === "error";
  const label = stageLabels[stage] ?? "Processing...";

  return (
    <div className="w-full space-y-2">
      <div className="flex justify-between text-xs text-slate-400">
        <span>{isError ? "Processing failed" : label}</span>
        <span>{progress}%</span>
      </div>
      <div className="w-full h-2 bg-[#242840] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isError ? "bg-red-500" : "bg-indigo-500"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}