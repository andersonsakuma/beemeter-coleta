package br.org.ipe.coletacampo;

import android.app.Activity;
import android.content.ClipData;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Arrays;

/**
 * Casca nativa mínima: carrega a coleta empacotada em assets/ num WebView, sem rede.
 * A ponte "ColetaApp" cuida do que o WebView não faz sozinho: compartilhar e salvar arquivos,
 * abrir a câmera, guardar fotos e ler o GPS.
 */
public class MainActivity extends Activity {
    private static final int PEDIR_ARQUIVO = 1, PEDIR_FOTO = 2, SALVAR = 3, PERMISSAO_GPS = 4;
    private WebView web;
    private ValueCallback<Uri[]> retorno;
    private Uri fotoUri;
    private File saindo;          // arquivo montado em partes pelo JavaScript
    private File salvarOrigem;    // arquivo à espera do local escolhido pelo usuário
    private String gpsPendente;
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#EEF2EC"));
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // localStorage guarda os registros
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);         // lê a foto devolvida pela câmera
        s.setUserAgentString(s.getUserAgentString() + " ColetaCampoApp");

        web.addJavascriptInterface(new Ponte(), "ColetaApp");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, String url) {
                return !url.startsWith("file:///android_asset/");
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (retorno != null) retorno.onReceiveValue(null);
                retorno = cb;
                boolean imagem = Arrays.toString(p.getAcceptTypes()).contains("image");
                if (imagem && p.isCaptureEnabled() && abrirCamera()) return true;
                try {
                    startActivityForResult(p.createIntent(), PEDIR_ARQUIVO);
                } catch (Exception e) {
                    retorno = null;
                    return false;
                }
                return true;
            }
        });

        if (b != null) web.restoreState(b);
        else web.loadUrl("file:///android_asset/index.html");
    }

    /** Câmera grava direto num arquivo do app (cache/camera), entregue ao WebView pelo provedor. */
    private boolean abrirCamera() {
        try {
            // sem resolveActivity: a partir do Android 11 ele não enxerga o app de câmera sem <queries>
            Intent i = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
            String nome = "foto-" + System.currentTimeMillis() + ".jpg";
            File f = new File(new File(getCacheDir(), "camera"), nome);
            f.getParentFile().mkdirs();
            fotoUri = Arquivos.uri("camera", nome);
            i.putExtra(MediaStore.EXTRA_OUTPUT, fotoUri);
            i.setClipData(ClipData.newRawUri("", fotoUri));
            i.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivityForResult(i, PEDIR_FOTO);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        if (req == PEDIR_ARQUIVO && retorno != null) {
            retorno.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data));
            retorno = null;
        } else if (req == PEDIR_FOTO && retorno != null) {
            retorno.onReceiveValue(res == RESULT_OK && fotoUri != null ? new Uri[]{fotoUri} : null);
            retorno = null;
        } else if (req == SALVAR) {
            if (res == RESULT_OK && data != null && data.getData() != null && salvarOrigem != null) {
                try {
                    OutputStream o = getContentResolver().openOutputStream(data.getData());
                    copiar(new FileInputStream(salvarOrigem), o);
                    aviso("Arquivo salvo");
                } catch (Exception e) {
                    aviso("Não foi possível salvar o arquivo");
                }
            }
            salvarOrigem = null;
        }
    }

    private static void copiar(InputStream in, OutputStream out) throws java.io.IOException {
        byte[] buf = new byte[65536];
        int n;
        try { while ((n = in.read(buf)) > 0) out.write(buf, 0, n); }
        finally { in.close(); out.close(); }
    }

    private void emitir(final JSONObject e) {
        final String js = "window.Coleta&&window.Coleta.evento(" + e.toString() + ")";
        main.post(new Runnable() { public void run() { web.evaluateJavascript(js, null); } });
    }

    private void aviso(String t) {
        try { emitir(new JSONObject().put("tipo", "aviso").put("texto", t)); } catch (Exception ignored) { }
    }

    /* ---------------- GPS ---------------- */
    private void gpsResposta(String id, Location l, String erro) {
        try {
            JSONObject e = new JSONObject().put("tipo", "gps").put("id", id);
            if (l != null) e.put("lat", l.getLatitude()).put("lon", l.getLongitude()).put("prec", l.getAccuracy());
            else e.put("erro", erro);
            emitir(e);
        } catch (Exception ignored) { }
    }

    private void lerGps(final String id) {
        final LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        try {
            Location ultima = null;
            for (String p : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
                Location l = null;
                try { l = lm.getLastKnownLocation(p); } catch (SecurityException ignored) { }   // só aproximada
                if (l != null && (ultima == null || l.getTime() > ultima.getTime())) ultima = l;
            }
            if (ultima != null && System.currentTimeMillis() - ultima.getTime() < 120000) { gpsResposta(id, ultima, null); return; }
            final boolean preciso = Build.VERSION.SDK_INT < 23
                    || checkSelfPermission("android.permission.ACCESS_FINE_LOCATION") == PackageManager.PERMISSION_GRANTED;
            final String prov = preciso ? LocationManager.GPS_PROVIDER : LocationManager.NETWORK_PROVIDER;
            if (!lm.isProviderEnabled(prov)) {
                if (ultima != null) gpsResposta(id, ultima, null);
                else gpsResposta(id, null, "Ligue a localização (GPS) do celular e tente de novo.");
                return;
            }
            final Location reserva = ultima;
            final boolean[] feito = {false};
            final LocationListener ouvinte = new LocationListener() {
                public void onLocationChanged(Location l) { if (!feito[0]) { feito[0] = true; gpsResposta(id, l, null); } }
                public void onStatusChanged(String p, int s, Bundle b) { }
                public void onProviderEnabled(String p) { }
                public void onProviderDisabled(String p) { }
            };
            lm.requestSingleUpdate(prov, ouvinte, Looper.getMainLooper());
            main.postDelayed(new Runnable() {
                public void run() {
                    if (feito[0]) return;
                    feito[0] = true;
                    try { lm.removeUpdates(ouvinte); } catch (SecurityException ignored) { }
                    if (reserva != null) gpsResposta(id, reserva, null);
                    else gpsResposta(id, null, "Sem sinal de GPS em 60 s. Tente num lugar aberto.");
                }
            }, 60000);
        } catch (SecurityException e) {
            gpsResposta(id, null, "Permissão de localização negada.");
        }
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        if (req != PERMISSAO_GPS || gpsPendente == null) return;
        String id = gpsPendente;
        gpsPendente = null;
        boolean alguma = false;
        for (int r : res) alguma |= r == PackageManager.PERMISSION_GRANTED;   // localização aproximada também serve
        if (alguma) lerGps(id);
        else gpsResposta(id, null, "Permissão de localização negada.");
    }

    @Override
    protected void onSaveInstanceState(Bundle b) {
        super.onSaveInstanceState(b);
        web.saveState(b);
    }

    @Override
    public void onBackPressed() {
        web.evaluateJavascript("(window.Coleta&&window.Coleta.voltar())?'1':'0'", new ValueCallback<String>() {
            public void onReceiveValue(String v) {
                if (!"\"1\"".equals(v)) MainActivity.super.onBackPressed();
            }
        });
    }

    /** Ponte para o JavaScript da coleta. */
    private class Ponte {
        /* arquivos de saída: o JavaScript manda em partes Base64 (o WebView não baixa blobs) */
        @JavascriptInterface
        public void arquivoInicio(String nome) {
            File dir = new File(getCacheDir(), "saida");
            dir.mkdirs();
            File[] velhos = dir.listFiles();
            if (velhos != null) for (File v : velhos) v.delete();
            saindo = new File(dir, nome.replaceAll("[^A-Za-z0-9._-]", "_"));
            saindo.delete();
        }

        @JavascriptInterface
        public void arquivoParte(String b64) {
            try {
                FileOutputStream o = new FileOutputStream(saindo, true);
                o.write(Base64.decode(b64, Base64.DEFAULT));
                o.close();
            } catch (Exception e) {
                aviso("Falha ao montar o arquivo");
            }
        }

        @JavascriptInterface
        public void arquivoFim(final String mime, final String titulo, final String modo) {
            final File f = saindo;
            main.post(new Runnable() {
                public void run() {
                    if ("salvar".equals(modo)) {
                        salvarOrigem = f;
                        Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                        i.addCategory(Intent.CATEGORY_OPENABLE);
                        i.setType(mime);
                        i.putExtra(Intent.EXTRA_TITLE, f.getName());
                        startActivityForResult(i, SALVAR);
                        return;
                    }
                    Uri u = Arquivos.uri("saida", f.getName());
                    Intent i = new Intent(Intent.ACTION_SEND);
                    i.setType(mime);
                    i.putExtra(Intent.EXTRA_STREAM, u);
                    i.putExtra(Intent.EXTRA_SUBJECT, titulo);
                    i.putExtra(Intent.EXTRA_TEXT, titulo + " — " + f.getName());
                    i.setClipData(ClipData.newRawUri("", u));
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(i, "Enviar " + f.getName()));
                }
            });
        }

        /* fotos ficam em files/fotos, fora do cache: só saem se o usuário desinstalar o app */
        private File pastaFotos() { File d = new File(getFilesDir(), "fotos"); d.mkdirs(); return d; }

        @JavascriptInterface
        public boolean fotoGravar(String nome, String b64) {
            if (!nome.matches("[A-Za-z0-9._-]+")) return false;
            try {
                FileOutputStream o = new FileOutputStream(new File(pastaFotos(), nome));
                o.write(Base64.decode(b64, Base64.DEFAULT));
                o.close();
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public String fotoLer(String nome) {
            if (!nome.matches("[A-Za-z0-9._-]+")) return "";
            File f = new File(pastaFotos(), nome);
            if (!f.exists()) return "";
            try {
                byte[] b = new byte[(int) f.length()];
                FileInputStream in = new FileInputStream(f);
                int lido = 0, n;
                while (lido < b.length && (n = in.read(b, lido, b.length - lido)) > 0) lido += n;
                in.close();
                return Base64.encodeToString(b, Base64.NO_WRAP);
            } catch (Exception e) {
                return "";
            }
        }

        @JavascriptInterface
        public String fotoNomes() {
            JSONArray a = new JSONArray();
            String[] n = pastaFotos().list();
            if (n != null) { Arrays.sort(n); for (String x : n) a.put(x); }
            return a.toString();
        }

        @JavascriptInterface
        public void localizacao(final String id) {
            main.post(new Runnable() {
                public void run() {
                    if (Build.VERSION.SDK_INT >= 23
                            && checkSelfPermission("android.permission.ACCESS_FINE_LOCATION") != PackageManager.PERMISSION_GRANTED
                            && checkSelfPermission("android.permission.ACCESS_COARSE_LOCATION") != PackageManager.PERMISSION_GRANTED) {
                        gpsPendente = id;
                        requestPermissions(new String[]{"android.permission.ACCESS_FINE_LOCATION",
                                "android.permission.ACCESS_COARSE_LOCATION"}, PERMISSAO_GPS);
                        return;
                    }
                    lerGps(id);
                }
            });
        }
    }
}
