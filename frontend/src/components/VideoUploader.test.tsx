import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { api } from "../api/client";
import { VideoUploader } from "./VideoUploader";

vi.mock("../api/client", () => ({ api: { upload: vi.fn() }, ApiError: Error }));

it("validates the file picker as well as drag and drop", () => {
  render(<VideoUploader meta={null} onUploaded={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Traffic video"), {
    target: { files: [new File(["bad"], "notes.txt", { type: "text/plain" })] },
  });
  expect(screen.getByText(/not a supported format/)).toBeInTheDocument();
  expect(api.upload).not.toHaveBeenCalled();
});

it("accepts the same video again after a failed attempt", async () => {
  vi.mocked(api.upload).mockRejectedValue(new Error("Try again"));
  render(<VideoUploader meta={null} onUploaded={vi.fn()} />);
  const input = screen.getByLabelText("Traffic video");
  const files = [new File(["video"], "traffic.mp4", { type: "video/mp4" })];
  fireEvent.change(input, { target: { files } });
  await screen.findByText("Try again");
  expect(input).toHaveValue("");
  fireEvent.change(input, { target: { files } });
  await waitFor(() => expect(api.upload).toHaveBeenCalledTimes(2));
});

it("prevents a second upload while one is in flight", () => {
  vi.mocked(api.upload).mockReturnValue(new Promise(() => {}));
  const { container } = render(<VideoUploader meta={null} onUploaded={vi.fn()} />);
  const files = [new File(["video"], "traffic.mp4")];
  fireEvent.change(screen.getByLabelText("Traffic video"), { target: { files } });
  fireEvent.drop(container.querySelector("[class*='border-dashed']")!, { dataTransfer: { files } });
  expect(api.upload).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Choose video" })).toBeDisabled();
});
