export interface Topic {
  id: string;
  name: string;
  description: string | null;
}

export interface TopicDetail extends Topic {
  resources?: Array<{
    id: string;
    title: string;
    type: string;
    url: string;
  }>;
}
