package com.alice.kerneltrace;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

public class TraceFileProvider extends ContentProvider {
    static Uri uriFor(Context context, File file) {
        try {
            File base = TraceUtils.baseDir(context).getCanonicalFile();
            File target = file.getCanonicalFile();
            if (!target.getParentFile().equals(base)) {
                throw new IllegalArgumentException("File is outside trace directory");
            }
            return new Uri.Builder().scheme("content")
                    .authority("com.alice.kerneltrace.files")
                    .appendPath(target.getName()).build();
        } catch (IOException error) {
            throw new IllegalArgumentException(error);
        }
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    private File resolve(Uri uri) throws FileNotFoundException {
        if (getContext() == null || uri.getLastPathSegment() == null) {
            throw new FileNotFoundException("Invalid URI");
        }
        try {
            File base = TraceUtils.baseDir(getContext()).getCanonicalFile();
            File file = new File(base, uri.getLastPathSegment()).getCanonicalFile();
            if (!file.getParentFile().equals(base) || !file.isFile()) {
                throw new FileNotFoundException(uri.toString());
            }
            return file;
        } catch (IOException error) {
            throw new FileNotFoundException(error.toString());
        }
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException("Read only");
        return ParcelFileDescriptor.open(resolve(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public String getType(Uri uri) {
        return "application/zip";
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
                        String[] selectionArgs, String sortOrder) {
        try {
            File file = resolve(uri);
            MatrixCursor cursor = new MatrixCursor(
                    new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
            cursor.addRow(new Object[]{file.getName(), file.length()});
            return cursor;
        } catch (FileNotFoundException error) {
            return new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,
                    OpenableColumns.SIZE});
        }
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("Read only");
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection,
                      String[] selectionArgs) {
        throw new UnsupportedOperationException("Read only");
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("Read only");
    }
}
