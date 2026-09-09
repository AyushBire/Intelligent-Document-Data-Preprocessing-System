interface Props {
  value: string;
  variant?: "type" | "status";
}

const typeColors: Record<string, string> = {
  invoice: "bg-blue-500/20 text-blue-400",
  receipt: "bg-green-500/20 text-green-400",
  aadhaar: "bg-orange-500/20 text-orange-400",
  aadhaar_card: "bg-orange-500/20 text-orange-400",
  pan: "bg-yellow-500/20 text-yellow-400",
  pan_card: "bg-yellow-500/20 text-yellow-400",
  passport: "bg-purple-500/20 text-purple-400",
  driving_license: "bg-cyan-500/20 text-cyan-400",
  bank_statement: "bg-pink-500/20 text-pink-400",
};

const statusColors: Record<string, string> = {
  pending: "bg-slate-500/20 text-slate-400",
  processing: "bg-yellow-500/20 text-yellow-400",
  done: "bg-green-500/20 text-green-400",
  error: "bg-red-500/20 text-red-400",
};

export default function StatusBadge({ value, variant = "type" }: Props) {
  const map = variant === "type" ? typeColors : statusColors;
  const color = map[value.toLowerCase()] ?? "bg-slate-500/20 text-slate-400";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-md text-xs font-medium ${color}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}