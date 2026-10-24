import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { UploadDialog } from "@/components/chat/upload-dialog";
import { LocaleProvider } from "@/lib/i18n";

describe("file upload placeholder", () => {
  it("states that files are not accepted", async () => {
    const user = userEvent.setup();
    render(
      <LocaleProvider>
        <UploadDialog open onOpenChange={() => undefined} />
      </LocaleProvider>,
    );

    expect(
      screen.getByText("Document upload is not enabled in Version 0.1. Files are not accepted, stored, or analyzed."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close" }));
  });
});
