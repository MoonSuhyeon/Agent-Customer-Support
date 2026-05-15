"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { useChangePassword, useChangeTransferPassword } from "@/lib/api/hooks";
import { passwordSchema, transferPasswordSchema } from "@/lib/schemas/settings";
import type { PasswordFormValues, TransferPasswordFormValues } from "@/lib/schemas/settings";

function PasswordForm() {
  const { mutateAsync, isPending } = useChangePassword();

  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current: "", next: "", confirm: "" },
  });

  const onSubmit = async (values: PasswordFormValues) => {
    try {
      await mutateAsync({ current: values.current, next: values.next });
      form.reset();
      toast({ title: "변경되었습니다.", description: "비밀번호가 변경되었습니다." });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "다시 시도해주세요.";
      toast({ title: "변경 실패", description: msg, variant: "destructive" });
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="current"
          render={({ field }) => (
            <FormItem>
              <FormLabel>현재 비밀번호</FormLabel>
              <FormControl>
                <Input type="password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="next"
          render={({ field }) => (
            <FormItem>
              <FormLabel>새 비밀번호</FormLabel>
              <FormControl>
                <Input type="password" placeholder="8자 이상" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="confirm"
          render={({ field }) => (
            <FormItem>
              <FormLabel>새 비밀번호 확인</FormLabel>
              <FormControl>
                <Input type="password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={isPending}>
            {isPending ? "변경 중..." : "변경"}
          </Button>
        </div>
      </form>
    </Form>
  );
}

function TransferPasswordForm() {
  const { mutateAsync, isPending } = useChangeTransferPassword();

  const form = useForm<TransferPasswordFormValues>({
    resolver: zodResolver(transferPasswordSchema),
    defaultValues: { current: "", next: "", confirm: "" },
  });

  const onSubmit = async (values: TransferPasswordFormValues) => {
    try {
      await mutateAsync({ current: values.current, next: values.next });
      form.reset();
      toast({ title: "변경되었습니다.", description: "이체 비밀번호가 변경되었습니다." });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "다시 시도해주세요.";
      toast({ title: "변경 실패", description: msg, variant: "destructive" });
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="current"
          render={({ field }) => (
            <FormItem>
              <FormLabel>현재 이체 비밀번호</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  maxLength={4}
                  inputMode="numeric"
                  placeholder="숫자 4자리"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="next"
          render={({ field }) => (
            <FormItem>
              <FormLabel>새 이체 비밀번호</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  maxLength={4}
                  inputMode="numeric"
                  placeholder="숫자 4자리"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="confirm"
          render={({ field }) => (
            <FormItem>
              <FormLabel>새 이체 비밀번호 확인</FormLabel>
              <FormControl>
                <Input
                  type="password"
                  maxLength={4}
                  inputMode="numeric"
                  placeholder="숫자 4자리"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={isPending}>
            {isPending ? "변경 중..." : "변경"}
          </Button>
        </div>
      </form>
    </Form>
  );
}

export function SecurityTab() {
  const [twoFactor, setTwoFactor] = useState(false);

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <h2 className="text-base font-semibold">비밀번호 변경</h2>
        <p className="text-sm text-muted-foreground">로그인 비밀번호를 변경합니다.</p>
      </div>
      <PasswordForm />

      <Separator />

      <div className="space-y-1">
        <h2 className="text-base font-semibold">이체 비밀번호 변경</h2>
        <p className="text-sm text-muted-foreground">이체 시 사용하는 4자리 비밀번호를 변경합니다.</p>
      </div>
      <TransferPasswordForm />

      <Separator />

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="two-factor" className="text-base font-semibold cursor-pointer">
            2단계 인증
          </Label>
          <p className="text-sm text-muted-foreground">
            로그인 시 추가 인증 수단을 사용합니다.
          </p>
        </div>
        <Switch
          id="two-factor"
          checked={twoFactor}
          onCheckedChange={(v) => {
            setTwoFactor(v);
            toast({
              title: v ? "2단계 인증 활성화" : "2단계 인증 비활성화",
              description: "설정이 저장되었습니다.",
            });
          }}
        />
      </div>
    </div>
  );
}
