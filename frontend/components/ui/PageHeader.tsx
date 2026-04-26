import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow?: string;
  title?: string;
  description?: string;
  action?: ReactNode;
};

export default function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: PageHeaderProps) {
  return (
    <div>
      {eyebrow && <div>{eyebrow}</div>}
      {title && <h1>{title}</h1>}
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}