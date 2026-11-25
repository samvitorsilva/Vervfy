import SwiftUI

@main
struct VervfyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .tint(VervfyPalette.accent)
        }
    }
}

// BEGIN GENERATED PALETTE — edit design-tokens.json.
enum VervfyPalette {
    static let background = Color(.sRGB, red: 0.04705882, green: 0.05490196, blue: 0.07843137, opacity: 1)
    static let surface = Color(.sRGB, red: 0.07058824, green: 0.08235294, blue: 0.11764706, opacity: 1)
    static let deep = Color(.sRGB, red: 0.03137255, green: 0.03921569, blue: 0.06274510, opacity: 1)
    static let surfaceRaised = Color(.sRGB, red: 0.08627451, green: 0.09803922, blue: 0.14509804, opacity: 1)
    static let controlSurface = Color(.sRGB, red: 0.07058824, green: 0.07843137, blue: 0.10980392, opacity: 1)
    static let surfaceHover = Color(.sRGB, red: 0.08627451, green: 0.09803922, blue: 0.13725490, opacity: 1)
    static let accent = Color(.sRGB, red: 0.03137255, green: 0.90588235, blue: 0.74509804, opacity: 1)
    static let endpoint = Color(.sRGB, red: 0.00784314, green: 0.87450980, blue: 0.71372549, opacity: 1)
    static let text = Color(.sRGB, red: 0.94901961, green: 0.95294118, blue: 0.96862745, opacity: 1)
    static let secondary = Color(.sRGB, red: 0.75294118, green: 0.77254902, blue: 0.81960784, opacity: 1)
    static let muted = Color(.sRGB, red: 0.62745098, green: 0.65882353, blue: 0.72941176, opacity: 1)
    static let highlight = Color(.sRGB, red: 1.00000000, green: 1.00000000, blue: 1.00000000, opacity: 1)
    static let inputBorder = Color(.sRGB, red: 0.51372549, green: 0.54509804, blue: 0.60784314, opacity: 1)
    static let danger = Color(.sRGB, red: 1.00000000, green: 0.41960784, blue: 0.47843137, opacity: 1)
}
// END GENERATED PALETTE
