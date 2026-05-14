export default function GraphView({
  image_url,
  caption,
}: {
  image_url: string;
  caption?: string;
}) {
  return (
    <figure data-testid="math-graph-view">
      <img src={image_url} alt={caption ?? "graph"} />
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
