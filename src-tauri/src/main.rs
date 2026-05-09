#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    Manager, State,
};

const BACKEND_URL: &str = "http://127.0.0.1:8765";

struct BackendProcess(Mutex<Option<Child>>);

fn iniciar_backend() -> Option<Child> {
    let dir = std::env::current_dir().ok()?;
    Command::new("uvicorn")
        .args([
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--log-level",
            "warning",
        ])
        .current_dir(dir)
        .spawn()
        .ok()
}

fn llamar_backend(ruta: &str) {
    let url = format!("{}{}", BACKEND_URL, ruta);
    std::thread::spawn(move || {
        let _ = reqwest::blocking::get(&url);
    });
}

#[tauri::command]
fn get_estado() -> String {
    match reqwest::blocking::get(format!("{}/estado", BACKEND_URL)) {
        Ok(r) => r.text().unwrap_or_else(|_| "{}".into()),
        Err(_) => "{\"error\": \"backend no disponible\"}".into(),
    }
}

#[tauri::command]
fn registrar_identidad() {
    llamar_backend("/registrar_identidad");
}

fn main() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
            }

            let proceso = iniciar_backend();
            if let Ok(mut guard) = app.state::<BackendProcess>().0.lock() {
                *guard = proceso;
            }

            let silenciar  = MenuItem::with_id(app, "silenciar",  "⏸  Silenciar GEM",      true, None::<&str>)?;
            let registrar  = MenuItem::with_id(app, "registrar",  "📷  Registrar mi cara",   true, None::<&str>)?;
            let estado_it  = MenuItem::with_id(app, "estado",     "📊  Ver estado",           true, None::<&str>)?;
            let sep        = PredefinedMenuItem::separator(app)?;
            let salir      = MenuItem::with_id(app, "salir",      "✕   Salir",               true, None::<&str>)?;

            let menu = Menu::with_items(app, &[&silenciar, &registrar, &estado_it, &sep, &salir])?;

            TrayIconBuilder::new()
                .tooltip("GEM — activo")
                .menu(&menu)
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "salir" => {
                        if let Ok(mut guard) = app.state::<BackendProcess>().0.lock() {
                            if let Some(ref mut child) = *guard {
                                let _ = child.kill();
                            }
                        }
                        app.exit(0);
                    }
                    "registrar" => llamar_backend("/registrar_identidad"),
                    "estado"    => llamar_backend("/estado"),
                    _           => {}
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_estado, registrar_identidad])
        .run(tauri::generate_context!())
        .expect("Error al iniciar GEM");
}