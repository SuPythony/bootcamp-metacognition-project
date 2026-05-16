export default function GraphView({
  image_url,
  caption,
}: {
  image_url?: string;
  data?: unknown;
  caption?: string;
}) {
  return (
    <figure data-testid="science-graph-view" className="space-y-2">
      {image_url && (
        <div className="rounded-md border border-rule bg-paper p-2">
          <img
            src={image_url}
            alt={caption ?? "graph"}
            className="block w-full rounded-sm"
          />
        </div>
      )}
      {caption && (
        <figcaption className="text-caption text-ink-soft italic flex items-start gap-2">
          <span className="text-ink-faint font-mono text-mono shrink-0">fig.</span>
          <span>{caption}</span>
        </figcaption>
      )}
    </figure>
  );
}
