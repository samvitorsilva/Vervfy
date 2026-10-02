export interface Account {
  id: string;
  username: string;
  email: string | null;
  created_at: number;
  photo_url: string | null;
  track_count: number;
}

export interface CsrfResponse {
  csrf_token: string;
}

export interface UploadStatus {
  id: string;
  status: "processing" | "completed" | "failed";
  error?: string | null;
  attempts?: number;
  track_id?: string;
}

export interface LibraryState {
  favorites: string[];
  playlists: Array<{
    id: string;
    name: string;
    trackIds: string[];
  }>;
}
