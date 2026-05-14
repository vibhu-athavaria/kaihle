import { useQuery, useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export interface ScriptParameter {
  name: string;
  type: string;
  required: boolean;
  default: string | null;
  description: string | null;
}

export interface ScriptDefinition {
  name: string;
  description: string;
  parameters: ScriptParameter[];
  requires_api_key: boolean;
  category: string;
}

export interface ScriptListResponse {
  scripts: ScriptDefinition[];
}

export interface ScriptExecuteRequest {
  parameters: Record<string, unknown>;
  env_vars: Record<string, string>;
}

export interface ScriptExecuteResponse {
  script_name: string;
  status: "completed" | "failed";
  output: string | null;
  error: string | null;
  return_code: number | null;
}

export function useScriptsList() {
  return useQuery({
    queryKey: ["scripts", "list"],
    queryFn: async () => {
      const response =
        await apiClient.get<ScriptListResponse>("/api/v1/scripts");
      return response.data;
    },
  });
}

export function useExecuteScript() {
  return useMutation({
    mutationFn: async ({
      scriptName,
      parameters,
      envVars,
    }: {
      scriptName: string;
      parameters: Record<string, unknown>;
      envVars: Record<string, string>;
    }) => {
      const response = await apiClient.post<ScriptExecuteResponse>(
        `/api/v1/scripts/${scriptName}/execute`,
        { parameters, env_vars: envVars } as ScriptExecuteRequest,
      );
      return response.data;
    },
  });
}
