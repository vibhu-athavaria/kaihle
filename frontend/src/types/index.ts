export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Child {
  id: string;
  parent_id: string;
  full_name: string;
  age: number;
  grade: string;
  created_at: string;
}

export interface Lesson {
  id: string;
  title: string;
  subject: string;
  icon: string;
  type: 'today' | 'upcoming';
  schedule?: string;
  child_id: string;
}

export interface ChatMessage {
  id: string;
  message: string;
  is_user: boolean;
  timestamp: string;
  child_id: string;
}

export interface AuthContextType {
  user: User | null;
  signUp: (email: string, password: string) => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  loading: boolean;
}