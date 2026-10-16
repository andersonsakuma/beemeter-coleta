package br.org.ipe.coletacampo;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import android.webkit.MimeTypeMap;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.List;

/**
 * Provedor mínimo de arquivos (sem a biblioteca androidx): expõe só as pastas cache/saida (planilha,
 * fotos e cópia que o usuário compartilha) e cache/camera (foto que o app de câmera grava).
 * URI: content://br.org.ipe.coletacampo.arquivos/&lt;pasta&gt;/&lt;nome&gt;
 */
public class Arquivos extends ContentProvider {
    static final String AUTORIDADE = "br.org.ipe.coletacampo.arquivos";

    static Uri uri(String pasta, String nome) {
        return Uri.parse("content://" + AUTORIDADE + "/" + pasta + "/" + Uri.encode(nome));
    }

    private File arquivo(Uri u) throws FileNotFoundException {
        List<String> seg = u.getPathSegments();
        if (seg.size() != 2) throw new FileNotFoundException(u.toString());
        String pasta = seg.get(0), nome = seg.get(1);
        if (!("saida".equals(pasta) || "camera".equals(pasta)) || nome.contains("/") || nome.contains(".."))
            throw new FileNotFoundException(u.toString());
        return new File(new File(getContext().getCacheDir(), pasta), nome);
    }

    @Override public boolean onCreate() { return true; }

    @Override
    public ParcelFileDescriptor openFile(Uri u, String modo) throws FileNotFoundException {
        File f = arquivo(u);
        if (modo.contains("w")) {
            f.getParentFile().mkdirs();
            try { f.createNewFile(); } catch (IOException e) { throw new FileNotFoundException(e.getMessage()); }
            return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_WRITE
                    | ParcelFileDescriptor.MODE_CREATE | ParcelFileDescriptor.MODE_TRUNCATE);
        }
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri u, String[] proj, String sel, String[] args, String ord) {
        File f;
        try { f = arquivo(u); } catch (FileNotFoundException e) { return null; }
        MatrixCursor c = new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
        c.addRow(new Object[]{f.getName(), f.length()});
        return c;
    }

    @Override
    public String getType(Uri u) {
        String nome = u.getLastPathSegment();
        if (nome == null) return "application/octet-stream";
        int p = nome.lastIndexOf('.');
        String t = p >= 0 ? MimeTypeMap.getSingleton().getMimeTypeFromExtension(nome.substring(p + 1).toLowerCase()) : null;
        if (nome.endsWith(".xlsx")) t = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        return t != null ? t : "application/octet-stream";
    }

    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
