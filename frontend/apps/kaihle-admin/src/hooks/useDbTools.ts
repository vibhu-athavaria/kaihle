import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface ImportResultResponse {
  status: "completed" | "failed";
  output: string | null;
  error: string | null;
  users_updated: number;
}

/**
 * Triggers a pg_dump on the server and downloads the resulting SQL file.
 * The server streams the response directly as an attachment.
 */
export function useExportDatabase() {
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post("/api/v1/db-tools/export", null, {
        responseType: "blob",
      });

      // Build a download link and click it programmatically
      const url = window.URL.createObjectURL(
        new Blob([response.data as BlobPart]),
      );
      const link = document.createElement("a");
      link.href = url;
      const date = new Date().toISOString().slice(0, 10);
      link.setAttribute("download", `kaihle_export_${date}.sql`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    },
  });
}

/**
 * Uploads a .sql dump file and imports it into the current database,
 * then resets all user passwords to `overridePassword`.
 */
export function useImportDatabase() {
  return useMutation({
    mutationFn: async ({
      file,
      overridePassword,
    }: {
      file: File;
      overridePassword: string;
    }): Promise<ImportResultResponse> => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("override_password", overridePassword);

      const response = await apiClient.post<ImportResultResponse>(
        "/api/v1/db-tools/import",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return response.data;
    },
  });
}
