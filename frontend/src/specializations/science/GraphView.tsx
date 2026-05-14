export default function GraphView({
  image_url,
  caption,
}: {
  image_url?: string;
  data?: unknown;
  caption?: string;
}) {
  return (
    <figure data-testid="science-graph-view">
      {image_url && <img src={image_url} alt={caption ?? "graph"} />}
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
