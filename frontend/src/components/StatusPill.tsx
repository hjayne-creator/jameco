interface Props {
  status: string;
}

export function StatusPill({ status }: Props) {
  let cls = "status-pill";
  if (status === "running") cls += " running";
  else if (status === "completed" || status === "done") cls += " completed";
  else if (status === "error") cls += " error";
  else if (status.startsWith("awaiting_checkpoint")) cls += " awaiting";
  return <span className={cls}>{status.replace("awaiting_checkpoint:", "checkpoint: ")}</span>;
}
