import { apiClient } from "./apiClient";

const SERVICE_NAME = "generate-service";

export const generateService = {
  async streamCode(prompt, onChunk) {
    return apiClient.postStream(
      SERVICE_NAME,
      "api/generate/",
      { prompt },
      onChunk
    );
  },
};
