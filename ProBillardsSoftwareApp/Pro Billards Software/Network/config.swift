import Foundation

enum Config {
    /// Base URL of the Rankings-Bot API. No trailing slash.
    /// - Debug/simulator: use http://127.0.0.1:8003 (API on same Mac)
    /// - Physical device: use your Mac’s IP, e.g. http://192.0.2.10
    static var apiBaseURL: String {
        #if DEBUG
        return "http://127.0.0.1:8003"
        #else
        return "https://www.probilliardssoftware.com"  // or your production URL
        #endif
    }
}
//  config.swift
//  Pro Billards Software
//
//  Created by Cody Example on 3/11/26.
//

