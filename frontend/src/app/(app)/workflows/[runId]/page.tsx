import { WorkflowRunDetail } from "@/components/workflows/workflow-run-detail";

type WorkflowRunPageProps = {
  params: Promise<{ runId: string }>;
};

export default async function WorkflowRunPage({ params }: WorkflowRunPageProps) {
  const { runId } = await params;
  const parsedRunId = Number.parseInt(runId, 10);
  return <WorkflowRunDetail runId={parsedRunId} />;
}
