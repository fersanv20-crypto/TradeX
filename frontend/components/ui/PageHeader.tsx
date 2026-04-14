type PageHeaderProps = {
  eyebrow?: string;
  title?: string;
  description?: string;
};

export default function PageHeader({
  eyebrow,
  title,
  description,
}: PageHeaderProps) {
  return (
    <div>
      {eyebrow && <div>{eyebrow}</div>}
      {title && <h1>{title}</h1>}
      {description && <p>{description}</p>}
    </div>
  );
}