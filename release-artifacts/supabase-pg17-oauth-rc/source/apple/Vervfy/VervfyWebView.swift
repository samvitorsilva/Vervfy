import SwiftUI
import WebKit

#if os(iOS)
import UIKit
#elseif os(macOS)
import AppKit
#endif

struct VervfyWebView: View {
    let url: URL
    @Binding var selectedDestination: ShellDestination
    @Binding var navigationIsVisible: Bool
    let controller: WebViewController

    var body: some View {
        #if os(iOS)
        NativeWebView(
            url: url,
            selectedDestination: $selectedDestination,
            navigationIsVisible: $navigationIsVisible,
            controller: controller
        )
        #elseif os(macOS)
        NativeWebView(
            url: url,
            selectedDestination: $selectedDestination,
            navigationIsVisible: $navigationIsVisible,
            controller: controller
        )
        #endif
    }
}

final class WebViewController {
    private weak var webView: WKWebView?

    func attach(_ webView: WKWebView) {
        self.webView = webView
    }

    func navigate(to destination: ShellDestination) {
        webView?.evaluateJavaScript(
            "document.querySelector('.rail [data-view=\"\(destination.rawValue)\"]')?.click()"
        )
    }

    func perform(_ action: String) {
        let selectors: [String: String] = [
            "addMusic": ".rail-import-button",
            "shortcuts": ".rail-shortcuts-button",
            "logout": ".rail-logout-button",
        ]
        guard let selector = selectors[action] else { return }
        webView?.evaluateJavaScript("document.querySelector('\(selector)')?.click()")
    }
}

private final class WebViewCoordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
    private var selectedDestination: Binding<ShellDestination>
    private var navigationIsVisible: Binding<Bool>
    private let serverHost: String
    init(
        url: URL,
        selectedDestination: Binding<ShellDestination>,
        navigationIsVisible: Binding<Bool>
    ) {
        self.serverHost = url.host ?? ""
        self.selectedDestination = selectedDestination
        self.navigationIsVisible = navigationIsVisible
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard
            message.name == "vervfyNavigation",
            let state = message.body as? [String: Any]
        else {
            return
        }

        DispatchQueue.main.async {
            self.navigationIsVisible.wrappedValue = state["ready"] as? Bool ?? false
            if
                let rawValue = state["selected"] as? String,
                let destination = ShellDestination(rawValue: rawValue)
            {
                self.selectedDestination.wrappedValue = destination
            }
        }
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard
            let targetURL = navigationAction.request.url,
            targetURL.host?.lowercased() != serverHost.lowercased(),
            navigationAction.navigationType == .linkActivated
        else {
            decisionHandler(.allow)
            return
        }

        decisionHandler(.cancel)
        #if os(iOS)
        UIApplication.shared.open(targetURL)
        #elseif os(macOS)
        NSWorkspace.shared.open(targetURL)
        #endif
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.evaluateJavaScript("window.__vervfyNativeShell?.report()")
    }
}

private let nativeShellScript = """
(() => {
  const style = document.createElement("style");
  style.textContent = ".rail{display:none!important}";
  const installStyle = () => {
    const root = document.head || document.documentElement;
    if (!root) {
      document.addEventListener("DOMContentLoaded", installStyle, { once: true });
      return;
    }
    root.append(style);
  };
  installStyle();

  let observedRail;
  let previousRail;
  let previousReady;
  let previousSelected;
  const report = () => {
    const rail = document.querySelector(".rail");
    if (rail !== observedRail) {
      observedRail = rail;
      if (rail) {
        new MutationObserver(report).observe(rail, {
          subtree: true,
          attributes: true,
          attributeFilter: ["aria-current"]
        });
      }
    }
    const selected = rail?.querySelector('[data-view][aria-current="page"]')?.dataset.view;
    const ready = Boolean(rail);
    if (
      rail === previousRail &&
      ready === previousReady &&
      (selected || "library") === previousSelected
    ) return;
    previousRail = rail;
    previousReady = ready;
    previousSelected = selected || "library";
    window.webkit.messageHandlers.vervfyNavigation.postMessage({
      ready,
      selected: previousSelected
    });
  };

  window.__vervfyNativeShell = { report };
  new MutationObserver(report).observe(document, {
    childList: true,
    subtree: true
  });
  report();
})();
"""

#if os(iOS)
private struct NativeWebView: UIViewRepresentable {
    let url: URL
    @Binding var selectedDestination: ShellDestination
    @Binding var navigationIsVisible: Bool
    let controller: WebViewController

    func makeCoordinator() -> WebViewCoordinator {
        WebViewCoordinator(
            url: url,
            selectedDestination: $selectedDestination,
            navigationIsVisible: $navigationIsVisible
        )
    }

    func makeUIView(context: Context) -> WKWebView {
        let contentController = WKUserContentController()
        contentController.add(context.coordinator, name: "vervfyNavigation")
        contentController.addUserScript(
            WKUserScript(
                source: nativeShellScript,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
        )

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = contentController
        let webView = WKWebView(frame: .zero, configuration: configuration)
        controller.attach(webView)
        webView.navigationDelegate = context.coordinator
        webView.isOpaque = false
        webView.backgroundColor = .systemBackground
        webView.scrollView.backgroundColor = .systemBackground
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}
}
#elseif os(macOS)
private struct NativeWebView: NSViewRepresentable {
    let url: URL
    @Binding var selectedDestination: ShellDestination
    @Binding var navigationIsVisible: Bool
    let controller: WebViewController

    func makeCoordinator() -> WebViewCoordinator {
        WebViewCoordinator(
            url: url,
            selectedDestination: $selectedDestination,
            navigationIsVisible: $navigationIsVisible
        )
    }

    func makeNSView(context: Context) -> WKWebView {
        let contentController = WKUserContentController()
        contentController.add(context.coordinator, name: "vervfyNavigation")
        contentController.addUserScript(
            WKUserScript(
                source: nativeShellScript,
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
        )

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = contentController
        let webView = WKWebView(frame: .zero, configuration: configuration)
        controller.attach(webView)
        webView.navigationDelegate = context.coordinator
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {}
}
#endif
