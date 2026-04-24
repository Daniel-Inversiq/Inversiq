import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type FeaturePlaceholderProps = {
  title: string;
  description: string;
};

export function FeaturePlaceholder({
  title,
  description,
}: FeaturePlaceholderProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}
