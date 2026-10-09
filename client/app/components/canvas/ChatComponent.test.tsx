import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatComponent from "./ChatComponent";
import { useChatStore } from "~/stores/chat";
import { AIBuilderService } from "~/services/aiBuilderService";
import { getUserCredentials, getUserCredentialById } from "~/services/userCredentialService";

vi.mock("~/services/aiBuilderService", () => ({
  AIBuilderService: { generateWorkflow: vi.fn() },
}));
vi.mock("~/services/userCredentialService", () => ({
  getUserCredentials: vi.fn(),
  getUserCredentialById: vi.fn(),
}));

const renderChat = () => render(
  <ChatComponent
    chatOpen={true}
    setChatOpen={vi.fn()}
    chatHistory={[]}
    chatError={null}
    chatLoading={false}
    chatThinking={false}
    chatInput=""
    setChatInput={vi.fn()}
    onSendMessage={vi.fn()}
    onClearChat={vi.fn()}
    activeChatflowId={null}
  />
);

describe("KAI Assistant errors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    useChatStore.setState({ builderChats: {}, activeBuilderChatflowId: null });
    vi.mocked(getUserCredentialById).mockResolvedValue({ secret: {} } as never);
  });

  it("shows missing credentials as a red response bubble", async () => {
    vi.mocked(getUserCredentials).mockResolvedValue([]);
    renderChat();
    fireEvent.click(screen.getByTitle("Switch to KAI Assistant"));
    fireEvent.change(screen.getByPlaceholderText("e.g. Create a simple chatbot..."), {
      target: { value: "Build a workflow" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Build" }));

    const error = await screen.findByText(/Please select an API Credential first/);
    expect(error.closest(".bg-red-950\\/90")).not.toBeNull();
    expect(AIBuilderService.generateWorkflow).not.toHaveBeenCalled();
  });

  it("shows provider errors as a red response bubble", async () => {
    vi.mocked(getUserCredentials).mockResolvedValue([
      { id: "credential-1", service_type: "openai" },
    ] as never);
    vi.mocked(AIBuilderService.generateWorkflow).mockRejectedValue({ message: "Provider unavailable" });
    renderChat();
    fireEvent.click(screen.getByTitle("Switch to KAI Assistant"));
    await waitFor(() => expect(getUserCredentialById).toHaveBeenCalledWith("credential-1"));
    fireEvent.change(screen.getByPlaceholderText("e.g. Create a simple chatbot..."), {
      target: { value: "Build a workflow" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Build" }));

    const error = await screen.findByText("Provider unavailable");
    expect(error.closest(".bg-red-950\\/90")).not.toBeNull();
  });

  it("retries a failed first build in build mode", async () => {
    vi.mocked(getUserCredentials).mockResolvedValue([
      { id: "credential-1", service_type: "openai" },
    ] as never);
    vi.mocked(AIBuilderService.generateWorkflow).mockRejectedValue({ message: "Provider unavailable" });
    renderChat();
    fireEvent.click(screen.getByTitle("Switch to KAI Assistant"));
    await waitFor(() => expect(getUserCredentialById).toHaveBeenCalledWith("credential-1"));

    const input = screen.getByPlaceholderText("e.g. Create a simple chatbot...");
    fireEvent.change(input, { target: { value: "First attempt" } });
    fireEvent.click(screen.getByRole("button", { name: "Build" }));
    await screen.findByText("Provider unavailable");

    fireEvent.change(input, { target: { value: "Try again" } });
    fireEvent.click(screen.getByRole("button", { name: "Build" }));
    await waitFor(() => expect(AIBuilderService.generateWorkflow).toHaveBeenCalledTimes(2));
    expect(vi.mocked(AIBuilderService.generateWorkflow).mock.calls[1][1].mode).toBe("build");
  });

  it("shows structured API errors without crashing the conversation", async () => {
    vi.mocked(getUserCredentials).mockResolvedValue([
      { id: "credential-1", service_type: "openai" },
    ] as never);
    vi.mocked(AIBuilderService.generateWorkflow).mockRejectedValue({
      message: [{ field: "credential_id", reason: "invalid" }],
    });
    renderChat();
    fireEvent.click(screen.getByTitle("Switch to KAI Assistant"));
    await waitFor(() => expect(getUserCredentialById).toHaveBeenCalledWith("credential-1"));
    fireEvent.change(screen.getByPlaceholderText("e.g. Create a simple chatbot..."), {
      target: { value: "Build a workflow" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Build" }));

    expect(await screen.findByText('[{"field":"credential_id","reason":"invalid"}]')).toBeTruthy();
  });

  it("renders a saved long builder error with expandable details", async () => {
    vi.mocked(getUserCredentials).mockResolvedValue([]);
    const detail = "Provider failure: " + "x".repeat(400);
    useChatStore.setState({
      activeBuilderChatflowId: "conversation-1",
      builderChats: {
        "conversation-1": [{
          id: "error-1",
          chatflow_id: "conversation-1",
          role: "error",
          content: detail,
          source_documents: "ai_builder",
          created_at: new Date().toISOString(),
        }],
      },
    });
    renderChat();
    fireEvent.click(screen.getByTitle("Switch to KAI Assistant"));

    const detailsButton = screen.getByRole("button", { name: "Show details" });
    expect(detailsButton.closest(".bg-red-950\\/90")).not.toBeNull();
    expect(screen.queryByText(detail)).toBeNull();
    fireEvent.click(detailsButton);
    expect(screen.getByText(detail)).toBeTruthy();
  });
});
