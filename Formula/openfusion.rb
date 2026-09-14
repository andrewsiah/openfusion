# Homebrew formula for OpenFusion. Lives in the tap repo andrewsiah/homebrew-tap as Formula/openfusion.rb;
# this copy is kept in sync in the main repo.
#   brew tap andrewsiah/tap && brew install andrewsiah/tap/openfusion      (or --HEAD for main)
class Openfusion < Formula
  include Language::Python::Virtualenv

  desc "Devin-Fusion-style orchestration on the AI subscriptions you already pay for"
  homepage "https://github.com/andrewsiah/openfusion"
  url "https://github.com/andrewsiah/openfusion/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "8c738f7d0705830eaa1e4d0b4f1648da819032a97c2508cd9d841caf88490435"
  license "MIT"
  head "https://github.com/andrewsiah/openfusion.git", branch: "main"

  depends_on "python@3.12"

  def install
    # Pure Python, zero dependencies: a venv with just this package.
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      fusion drives the coding-agent CLIs you already use. Install and log in to the ones you need:
        npm i -g @anthropic-ai/claude-code   (lead / sidekick / reviewer on your Claude plan)
        npm i -g @openai/codex               (sidekick / reviewer on your ChatGPT plan)
        npm i -g @mariozechner/pi-coding-agent  + OPENROUTER_API_KEY  (any BYOK model)
      Then run:  fusion doctor
    EOS
  end

  test do
    assert_match "fusion 0.1.0", shell_output("#{bin}/fusion --version")
    assert_match "fusion-delegate error", shell_output("#{bin}/fusion-delegate 2>&1", 2)
  end
end
