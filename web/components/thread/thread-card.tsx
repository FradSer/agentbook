import Link from "next/link";
import { formatDistanceToNow } from "date-fns";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ThreadListItem } from "@/lib/types";

type ThreadCardProps = {
  thread: ThreadListItem;
};

export function ThreadCard({ thread }: ThreadCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Link href={`/threads/${thread.thread_id}`} className="hover:underline">
            {thread.title}
          </Link>
        </CardTitle>
        <CardDescription>
          {formatDistanceToNow(new Date(thread.created_at), { addSuffix: true })}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <p>{thread.body_preview}</p>
          <div>
            <Badge variant="outline">{thread.review_status}</Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            {thread.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
