nombre: Firmware base
descripcion: app externa (FAP) para Flipper Zero: manifiesto + bucle de eventos con ViewPort
lenguaje: c
orden: 40
---
Escríbeme una app externa (FAP) para Flipper Zero que: <describe aquí qué debe hacer>
Parte de este andamiaje (application.fam + bucle de eventos con ViewPort, salida con el botón Atrás),
compatible con el firmware oficial y con forks tipo Momentum, y explícame cómo compilarla con `ufbt`.

application.fam
```python
App(
    appid="mi_app",
    name="Mi App",
    apptype=FlipperAppType.EXTERNAL,
    entry_point="mi_app_main",
    requires=["gui"],
    stack_size=2 * 1024,
    fap_category="Tools",
)
```

mi_app.c
```c
#include <furi.h>
#include <gui/gui.h>
#include <input/input.h>

typedef struct {
    FuriMessageQueue* eventos;
    ViewPort* view_port;
    Gui* gui;
} MiApp;

static void dibujar(Canvas* canvas, void* ctx) {
    UNUSED(ctx);
    canvas_clear(canvas);
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str(canvas, 2, 12, "Mi App");
    canvas_set_font(canvas, FontSecondary);
    canvas_draw_str(canvas, 2, 28, "Atras para salir");
}

static void entrada(InputEvent* ev, void* ctx) {
    MiApp* app = ctx;
    furi_message_queue_put(app->eventos, ev, FuriWaitForever);
}

int32_t mi_app_main(void* p) {
    UNUSED(p);
    MiApp app = {0};
    app.eventos = furi_message_queue_alloc(8, sizeof(InputEvent));
    app.view_port = view_port_alloc();
    view_port_draw_callback_set(app.view_port, dibujar, &app);
    view_port_input_callback_set(app.view_port, entrada, &app);
    app.gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(app.gui, app.view_port, GuiLayerFullscreen);

    InputEvent ev;
    bool seguir = true;
    while(seguir) {
        if(furi_message_queue_get(app.eventos, &ev, 100) == FuriStatusOk) {
            if(ev.type == InputTypeShort && ev.key == InputKeyBack) seguir = false;
            // TODO: resto de teclas
        }
        view_port_update(app.view_port);
    }

    gui_remove_view_port(app.gui, app.view_port);
    furi_record_close(RECORD_GUI);
    view_port_free(app.view_port);
    furi_message_queue_free(app.eventos);
    return 0;
}
```
